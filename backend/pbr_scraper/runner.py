"""
Main runner for PBR scraping pipeline.
Ties together commitments scraper, profile scraper, and school scraper.
Supports checkpointing so scraping can be interrupted and resumed.

Output: backend/data/rescraped/pbr_all_players.csv (single big CSV with all players)

Usage:
    # Full pipeline (classes 2022-2027)
    python3 -m backend.pbr_scraper.runner

    # Only collect commitment URLs (fast, ~30 min)
    python3 -m backend.pbr_scraper.runner --commitments-only

    # Only scrape profiles (assumes commitments CSV already exists)
    python3 -m backend.pbr_scraper.runner --profiles-only

    # Scrape specific class years
    python3 -m backend.pbr_scraper.runner --years 2025 2026 2027

    # Resume from checkpoint after interruption
    python3 -m backend.pbr_scraper.runner --profiles-only

    # Retry previously failed URLs
    python3 -m backend.pbr_scraper.runner --retry-failed

    # Run with visible browser (for debugging)
    python3 -m backend.pbr_scraper.runner --visible
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import threading
from concurrent.futures import ThreadPoolExecutor

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_info_scraper.selenium_driver import SeleniumDriverManager
from backend.pbr_scraper.config import (
    CLASS_YEARS,
    BETWEEN_PROFILES_DELAY,
    PAGE_LOAD_DELAY,
    OUTPUT_DIR,
    CHECKPOINT_PATH,
    COMMITMENTS_CSV_PATH,
    ALL_PLAYERS_CSV_PATH,
    SCHOOL_CACHE_PATH,
    ALL_STAT_COLUMNS,
    STATE_TO_REGION,
    PBR_BASE_URL,
    classify_commitment_group,
)
from backend.pbr_scraper.commitments_scraper import CommitmentsScraper
from backend.pbr_scraper.profile_scraper import ProfileScraper
from backend.pbr_scraper.school_scraper import SchoolScraper

# Setup logging (file handler added in main() after output dir is ensured)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# CSV columns for the output file
CSV_COLUMNS = [
    # Player info
    "name", "link", "player_state", "high_school", "class",
    "primary_position", "commitment", "commitment_date", "age", "positions",
    "height", "weight", "throwing_hand", "hitting_handedness",
]

# Add stat columns with dates
for stat in ALL_STAT_COLUMNS:
    CSV_COLUMNS.append(stat)
    CSV_COLUMNS.append(f"{stat}_date")

# Add school/derived columns
CSV_COLUMNS.extend([
    "player_region",
    "conference", "division", "college_location",
    "committment_group",
    "scraped_at",
])


class Checkpoint:
    """Manages scraping progress for resume capability"""

    def __init__(self):
        self._lock = threading.Lock()
        self.scraped_urls = set()
        self.failed_urls = set()
        self.last_class_year = None
        self.last_page = 0
        self._load()

    def _load(self):
        if os.path.exists(CHECKPOINT_PATH):
            with open(CHECKPOINT_PATH, "r") as f:
                data = json.load(f)
            self.scraped_urls = set(data.get("scraped_urls", []))
            self.failed_urls = set(data.get("failed_urls", []))
            self.last_class_year = data.get("last_class_year")
            self.last_page = data.get("last_page", 0)
            logger.info(
                f"Checkpoint loaded: {len(self.scraped_urls)} scraped, "
                f"{len(self.failed_urls)} failed"
            )

    def save(self):
        with self._lock:
            os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
            data = {
                "scraped_urls": list(self.scraped_urls),
                "failed_urls": list(self.failed_urls),
                "last_class_year": self.last_class_year,
                "last_page": self.last_page,
                "updated_at": datetime.now().isoformat(),
            }
            with open(CHECKPOINT_PATH, "w") as f:
                json.dump(data, f)

    def mark_scraped(self, url: str):
        with self._lock:
            self.scraped_urls.add(url)
            self.failed_urls.discard(url)

    def mark_failed(self, url: str):
        with self._lock:
            self.failed_urls.add(url)

    def is_scraped(self, url: str) -> bool:
        with self._lock:
            return url in self.scraped_urls


class SharedSchoolCache:
    """Thread-safe school info cache shared across parallel workers"""

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}
        if os.path.exists(SCHOOL_CACHE_PATH):
            with open(SCHOOL_CACHE_PATH, "r") as f:
                self._cache = json.load(f)
            logger.info(f"Loaded {len(self._cache)} schools from shared cache")

    def get(self, key):
        with self._lock:
            return self._cache.get(key)

    def put(self, key, value):
        with self._lock:
            self._cache[key] = value

    def save(self):
        with self._lock:
            os.makedirs(os.path.dirname(SCHOOL_CACHE_PATH), exist_ok=True)
            with open(SCHOOL_CACHE_PATH, "w") as f:
                json.dump(self._cache, f, indent=2)

    @property
    def size(self):
        with self._lock:
            return len(self._cache)


class ParallelSchoolScraper(SchoolScraper):
    """School scraper backed by a shared thread-safe cache instead of its own"""

    def __init__(self, driver_manager, shared_cache: SharedSchoolCache):
        # Skip parent __init__ to avoid loading a separate cache from disk
        self.driver_manager = driver_manager
        self._shared_cache = shared_cache

    def get_school_info(self, school_slug):
        slug = school_slug.lstrip("/")
        if not slug.startswith("schools/"):
            slug = f"schools/{slug}"

        cached = self._shared_cache.get(slug)
        if cached is not None:
            return cached

        info = self._scrape_school(slug)
        self._shared_cache.put(slug, info)
        return info

    @property
    def cache_size(self):
        return self._shared_cache.size


class ThreadSafeCSVWriter:
    """Thread-safe CSV writer for parallel workers"""

    def __init__(self, path, fieldnames):
        self._lock = threading.Lock()
        file_exists = os.path.exists(path)
        self._file = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._file, fieldnames=fieldnames, extrasaction="ignore"
        )
        if not file_exists:
            self._writer.writeheader()

    def writerow(self, row):
        with self._lock:
            self._writer.writerow(row)
            self._file.flush()

    def close(self):
        self._file.close()


def _worker_scrape_profiles(
    worker_id: int,
    players: List[Dict[str, str]],
    checkpoint: Checkpoint,
    csv_writer: ThreadSafeCSVWriter,
    shared_school_cache: SharedSchoolCache,
    delay: float,
    headless: bool,
    stop_event: threading.Event,
    progress: Dict,
    progress_lock: threading.Lock,
):
    """Worker function: creates its own browser and scrapes assigned profiles"""
    worker_log = logging.getLogger(f"worker-{worker_id}")
    worker_log.info(f"Starting with {len(players)} profiles assigned")

    driver_manager = SeleniumDriverManager(
        headless=headless, delay=delay, timeout=30,
    )
    profile_scraper = ProfileScraper(driver_manager)
    school_scraper = ParallelSchoolScraper(driver_manager, shared_school_cache)

    scraped = 0
    try:
        for i, player_info in enumerate(players):
            if stop_event.is_set():
                worker_log.info("Stop signal received, exiting")
                break

            url = player_info["profile_url"]
            if checkpoint.is_scraped(url):
                continue

            worker_log.info(
                f"[W{worker_id}] [{i + 1}/{len(players)}] {player_info.get('name', url)}"
            )

            profile_data = profile_scraper.scrape_profile(url)

            if profile_data is None:
                worker_log.warning(f"Failed: {url}")
                checkpoint.mark_failed(url)
                checkpoint.save()
                time.sleep(delay)
                continue

            # Merge: commitments page info + profile data (profile wins when non-empty)
            merged = {**player_info}
            for key, value in profile_data.items():
                if value is not None and value != "":
                    merged[key] = value
                elif key not in merged:
                    merged[key] = value

            # School enrichment
            school_link = merged.get("school_link", "")
            if school_link:
                school_info = school_scraper.get_school_info(school_link)
                merged["conference"] = school_info.get("conference", "")
                merged["division"] = school_info.get("division", "")
                merged["college_location"] = school_info.get("location", "")
                merged["committment_group"] = classify_commitment_group(
                    merged.get("division", ""),
                    merged.get("conference", ""),
                )

            # Derive region
            state = merged.get("player_state", "")
            merged["player_region"] = STATE_TO_REGION.get(state, "")
            merged["scraped_at"] = datetime.now().isoformat()

            csv_writer.writerow(merged)
            checkpoint.mark_scraped(url)
            scraped += 1

            # Global progress tracking
            with progress_lock:
                progress["scraped"] += 1
                total_scraped = progress["scraped"]

            if total_scraped % 50 == 0:
                checkpoint.save()
                shared_school_cache.save()
                logger.info(
                    f"Global progress: {total_scraped}/{progress['total']} profiles "
                    f"(school cache: {shared_school_cache.size})"
                )

            time.sleep(delay)

    except Exception as e:
        worker_log.error(f"Worker {worker_id} error: {e}", exc_info=True)
    finally:
        driver_manager.close()
        worker_log.info(f"Finished. Scraped {scraped} profiles.")


def run_profiles_parallel(
    players: List[Dict[str, str]],
    checkpoint: Checkpoint,
    num_workers: int,
    delay: float,
    headless: bool,
):
    """Scrape profiles using multiple parallel browser instances"""
    logger.info("=" * 60)
    logger.info(f"PHASE 2: Scraping profiles with {num_workers} parallel workers")
    logger.info("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Filter already scraped
    remaining = [p for p in players if not checkpoint.is_scraped(p["profile_url"])]
    logger.info(
        f"{len(remaining)} profiles to scrape "
        f"({len(players) - len(remaining)} already done)"
    )

    if not remaining:
        logger.info("Nothing to scrape.")
        return

    # Distribute URLs round-robin across workers
    chunks = [[] for _ in range(num_workers)]
    for i, player in enumerate(remaining):
        chunks[i % num_workers].append(player)

    for i, chunk in enumerate(chunks):
        logger.info(f"Worker {i}: {len(chunk)} profiles assigned")

    # Shared resources
    shared_school_cache = SharedSchoolCache()
    csv_writer = ThreadSafeCSVWriter(ALL_PLAYERS_CSV_PATH, CSV_COLUMNS)
    stop_event = threading.Event()
    progress = {"scraped": 0, "total": len(remaining)}
    progress_lock = threading.Lock()

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(
                    _worker_scrape_profiles,
                    worker_id,
                    chunks[worker_id],
                    checkpoint,
                    csv_writer,
                    shared_school_cache,
                    delay,
                    headless,
                    stop_event,
                    progress,
                    progress_lock,
                )
                futures.append(future)

            # Wait for all workers (KeyboardInterrupt will propagate)
            for future in futures:
                future.result()

    except KeyboardInterrupt:
        logger.info("Interrupted! Signaling workers to stop...")
        stop_event.set()
    finally:
        csv_writer.close()
        checkpoint.save()
        shared_school_cache.save()

    logger.info("=" * 60)
    logger.info(f"PARALLEL SCRAPING COMPLETE")
    logger.info(f"Scraped: {len(checkpoint.scraped_urls)}")
    logger.info(f"Failed: {len(checkpoint.failed_urls)}")
    logger.info(f"School cache: {shared_school_cache.size}")
    logger.info(f"Output: {ALL_PLAYERS_CSV_PATH}")
    logger.info("=" * 60)


def run_commitments_phase(
    driver_manager: SeleniumDriverManager,
    class_years: List[int],
) -> List[Dict[str, str]]:
    """Phase 1: Collect all player URLs from commitments pages"""
    logger.info("=" * 60)
    logger.info("PHASE 1: Collecting player URLs from commitments pages")
    logger.info("=" * 60)

    scraper = CommitmentsScraper(driver_manager)
    players = scraper.scrape_all_classes(class_years)

    logger.info(f"Phase 1 complete: {len(players)} player URLs collected")
    return players


def run_profiles_phase(
    driver_manager: SeleniumDriverManager,
    players: List[Dict[str, str]],
    checkpoint: Checkpoint,
    school_scraper: SchoolScraper,
) -> int:
    """Phase 2: Scrape each player profile and enrich with school data"""
    logger.info("=" * 60)
    logger.info("PHASE 2: Scraping player profiles")
    logger.info("=" * 60)

    profile_scraper = ProfileScraper(driver_manager)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Filter out already-scraped URLs
    remaining = [
        p for p in players if not checkpoint.is_scraped(p["profile_url"])
    ]
    logger.info(
        f"{len(remaining)} profiles to scrape "
        f"({len(players) - len(remaining)} already done)"
    )

    # Open CSV in append mode
    file_exists = os.path.exists(ALL_PLAYERS_CSV_PATH)
    csv_file = open(ALL_PLAYERS_CSV_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS, extrasaction="ignore")

    if not file_exists:
        writer.writeheader()

    scraped_count = 0

    try:
        for i, player_info in enumerate(remaining):
            url = player_info["profile_url"]

            logger.info(
                f"[{i + 1}/{len(remaining)}] Scraping: {player_info.get('name', url)}"
            )

            # Scrape profile
            profile_data = profile_scraper.scrape_profile(url)

            if profile_data is None:
                logger.warning(f"Failed to scrape: {url}")
                checkpoint.mark_failed(url)
                checkpoint.save()
                time.sleep(BETWEEN_PROFILES_DELAY)
                continue

            # Merge commitments page info with profile data
            # Profile data takes precedence only when non-empty,
            # so commitments page values (state, HS, etc.) aren't overwritten by blanks
            merged = {**player_info}
            for key, value in profile_data.items():
                if value is not None and value != "":
                    merged[key] = value
                elif key not in merged:
                    merged[key] = value

            # Enrich with school data
            school_link = merged.get("school_link", "")
            if school_link:
                school_info = school_scraper.get_school_info(school_link)
                merged["conference"] = school_info.get("conference", "")
                merged["division"] = school_info.get("division", "")
                merged["college_location"] = school_info.get("location", "")
                merged["committment_group"] = classify_commitment_group(
                    merged.get("division", ""),
                    merged.get("conference", ""),
                )

            # Derive region from state
            state = merged.get("player_state", "")
            merged["player_region"] = STATE_TO_REGION.get(state, "")

            # Add timestamp
            merged["scraped_at"] = datetime.now().isoformat()

            # Write to CSV
            writer.writerow(merged)
            csv_file.flush()

            # Update checkpoint
            checkpoint.mark_scraped(url)
            scraped_count += 1

            # Save checkpoint periodically
            if scraped_count % 25 == 0:
                checkpoint.save()
                logger.info(
                    f"Progress: {scraped_count}/{len(remaining)} profiles scraped "
                    f"(school cache: {school_scraper.cache_size})"
                )

            time.sleep(BETWEEN_PROFILES_DELAY)

    except KeyboardInterrupt:
        logger.info("Interrupted by user. Saving progress...")
    finally:
        csv_file.close()
        checkpoint.save()

    logger.info(f"Phase 2 complete: {scraped_count} profiles scraped")
    return scraped_count


def run_retry_failed(
    driver_manager: SeleniumDriverManager,
    checkpoint: Checkpoint,
    school_scraper: SchoolScraper,
):
    """Retry previously failed URLs"""
    failed = list(checkpoint.failed_urls)
    if not failed:
        logger.info("No failed URLs to retry")
        return

    logger.info(f"Retrying {len(failed)} failed URLs...")

    # Convert to player info format
    players = [{"profile_url": url, "name": url.split("/")[-1]} for url in failed]

    run_profiles_phase(driver_manager, players, checkpoint, school_scraper)


def main():
    parser = argparse.ArgumentParser(description="PBR Player Profile Scraper")
    parser.add_argument(
        "--commitments-only",
        action="store_true",
        help="Only collect commitment URLs (Phase 1)",
    )
    parser.add_argument(
        "--profiles-only",
        action="store_true",
        help="Only scrape profiles (assumes commitments CSV exists)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed URLs",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=CLASS_YEARS,
        help="Class years to scrape (e.g., --years 2025 2026 2027)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run browser in visible mode (not headless)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Base delay between requests in seconds",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel browser instances (e.g., --workers 4)",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Re-configure file handler now that output dir exists
    file_handler = logging.FileHandler(
        os.path.join(OUTPUT_DIR, "scraper.log")
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(file_handler)

    logger.info("=" * 60)
    logger.info("PBR Scraper Starting")
    logger.info(f"Class years: {args.years}")
    logger.info(f"Headless: {not args.visible}")
    logger.info(f"Workers: {args.workers}")
    logger.info("=" * 60)

    # Initialize checkpoint
    checkpoint = Checkpoint()
    headless = not args.visible

    # Parallel mode: workers handle their own drivers
    if args.workers > 1:
        # Phase 1 needs a single driver for commitments page
        if not args.profiles_only and not args.retry_failed:
            driver_manager = SeleniumDriverManager(
                headless=headless, delay=args.delay, timeout=30,
            )
            try:
                players = run_commitments_phase(driver_manager, args.years)
            finally:
                driver_manager.close()

            if args.commitments_only:
                logger.info("Commitments-only mode. Stopping after Phase 1.")
                return
        elif args.profiles_only:
            players = CommitmentsScraper.load_from_csv()
            if not players:
                logger.error(
                    f"No commitments CSV found at {COMMITMENTS_CSV_PATH}. "
                    "Run without --profiles-only first."
                )
                return
        elif args.retry_failed:
            failed = list(checkpoint.failed_urls)
            if not failed:
                logger.info("No failed URLs to retry")
                return
            logger.info(f"Retrying {len(failed)} failed URLs...")
            players = [
                {"profile_url": url, "name": url.split("/")[-1]}
                for url in failed
            ]
        else:
            players = []

        # Phase 2: Parallel profile scraping
        run_profiles_parallel(
            players, checkpoint, args.workers, args.delay, headless,
        )
        return

    # Single-worker mode (original behavior)
    driver_manager = SeleniumDriverManager(
        headless=headless, delay=args.delay, timeout=30,
    )
    school_scraper = SchoolScraper(driver_manager)

    try:
        if args.retry_failed:
            run_retry_failed(driver_manager, checkpoint, school_scraper)
            return

        # Phase 1: Collect commitment URLs
        if not args.profiles_only:
            players = run_commitments_phase(driver_manager, args.years)
        else:
            players = CommitmentsScraper.load_from_csv()
            if not players:
                logger.error(
                    f"No commitments CSV found at {COMMITMENTS_CSV_PATH}. "
                    "Run without --profiles-only first."
                )
                return

        if args.commitments_only:
            logger.info("Commitments-only mode. Stopping after Phase 1.")
            return

        # Phase 2: Scrape profiles
        run_profiles_phase(driver_manager, players, checkpoint, school_scraper)

        # Summary
        logger.info("=" * 60)
        logger.info("SCRAPING COMPLETE")
        logger.info(f"Scraped: {len(checkpoint.scraped_urls)}")
        logger.info(f"Failed: {len(checkpoint.failed_urls)}")
        logger.info(f"School cache: {school_scraper.cache_size}")
        logger.info(f"Output: {ALL_PLAYERS_CSV_PATH}")
        logger.info("=" * 60)

    finally:
        driver_manager.close()
        checkpoint.save()


if __name__ == "__main__":
    main()
