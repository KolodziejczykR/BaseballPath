"""
Fast targeted re-scrape to patch missing offspeed pitching stats.

The original scrape missed changeup/curveball/slider data because
Selenium's h4.text returned "CHANGEUP" (uppercase) while PITCH_SECTIONS
maps "Changeup" (title case). This script:

1. Loads the existing CSV
2. For each player that has fastball data but no offspeed data,
   fetches the page source and extracts offspeed stats via regex
3. Patches the CSV in-place (writes to a new file, not the original)

Uses parallel workers like the main scraper.

Usage:
    caffeinate -i python3 -m backend.pbr_scraper.patch_offspeed --workers 5 --delay 2
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_info_scraper.selenium_driver import SeleniumDriverManager
from backend.pbr_scraper.config import (
    OUTPUT_DIR,
    ALL_PLAYERS_CSV_PATH,
    PITCH_SECTIONS,
    PITCH_STAT_SUFFIX,
    PAGE_LOAD_DELAY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OFFSPEED_COLS = [
    "changeup_velo_range", "changeup_velo_range_date",
    "changeup_spin", "changeup_spin_date",
    "curveball_velo_range", "curveball_velo_range_date",
    "curveball_spin", "curveball_spin_date",
    "slider_velo_range", "slider_velo_range_date",
    "slider_spin", "slider_spin_date",
]

PATCHED_CSV_PATH = os.path.join(OUTPUT_DIR, "pbr_all_players_patched.csv")
PATCH_CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "patch_checkpoint.json")


def extract_offspeed_from_source(page_source: str) -> dict:
    """Extract offspeed pitching stats from page source HTML using regex."""
    stats = {}

    pitch_match = re.search(
        r'class="bestof-chart__row bestof-chart__pitching">(.*?)'
        r'(?=class="bestof-chart__row bestof-chart__|</section>)',
        page_source, re.DOTALL,
    )
    if not pitch_match:
        return stats

    pitch_html = pitch_match.group(1)

    stat_pattern = re.compile(
        r'<article\s+class="stat-item">\s*'
        r'<div\s+class="stat-v[^"]*">\s*(.*?)\s*</div>\s*'
        r'<div\s+class="stat-label">\s*(.*?)\s*</div>\s*'
        r'<div\s+class="stat-date">\s*(.*?)\s*</div>\s*'
        r'</article>',
        re.DOTALL,
    )

    # Split by h4 tags to track pitch type context
    parts = re.split(r'<h4>(.*?)</h4>', pitch_html)
    current_pitch = "fastball"

    for i, part in enumerate(parts):
        if i % 2 == 1:
            pitch_name = part.strip()
            prefix = PITCH_SECTIONS.get(pitch_name)
            if prefix:
                current_pitch = prefix
            continue

        # Skip fastball — we already have that data
        if current_pitch == "fastball":
            continue

        for m in stat_pattern.finditer(part):
            value = m.group(1).strip()
            label = m.group(2).strip()
            date = m.group(3).strip() or ""

            if value in ("-", ""):
                continue

            suffix = PITCH_STAT_SUFFIX.get(label)
            if suffix:
                col_name = f"{current_pitch}_{suffix}"
                stats[col_name] = value
                stats[f"{col_name}_date"] = date

    return stats


def load_checkpoint():
    """Load set of already-patched URLs."""
    if os.path.exists(PATCH_CHECKPOINT_PATH):
        with open(PATCH_CHECKPOINT_PATH, "r") as f:
            return set(json.load(f).get("patched_urls", []))
    return set()


def save_checkpoint(patched_urls):
    """Save patched URLs to checkpoint."""
    with open(PATCH_CHECKPOINT_PATH, "w") as f:
        json.dump({
            "patched_urls": list(patched_urls),
            "updated_at": datetime.now().isoformat(),
        }, f)


def worker_patch(
    worker_id, rows, delay, headless,
    results_lock, results_dict, patched_set, patched_lock,
    progress, progress_lock, stop_event,
):
    """Worker: fetch page source and extract offspeed stats for assigned rows."""
    wlog = logging.getLogger(f"patch-w{worker_id}")
    driver_manager = SeleniumDriverManager(headless=headless, delay=delay, timeout=30)

    patched = 0
    try:
        for i, row in enumerate(rows):
            if stop_event.is_set():
                break

            url = row["link"]

            with patched_lock:
                if url in patched_set:
                    continue

            wlog.info(f"[W{worker_id}] [{i+1}/{len(rows)}] {row.get('name', url)}")

            if not driver_manager.get(url, custom_delay=PAGE_LOAD_DELAY):
                time.sleep(delay)
                continue

            driver = driver_manager.driver

            # Scroll to trigger lazy load
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(0.5)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
            except Exception:
                pass

            try:
                source = driver.page_source
            except Exception:
                time.sleep(delay)
                continue

            offspeed = extract_offspeed_from_source(source)

            if offspeed:
                with results_lock:
                    results_dict[url] = offspeed
                patched += 1

            with patched_lock:
                patched_set.add(url)

            with progress_lock:
                progress["done"] += 1
                done = progress["done"]

            if done % 100 == 0:
                with patched_lock:
                    save_checkpoint(patched_set)
                logger.info(
                    f"Progress: {done}/{progress['total']} checked, "
                    f"{len(results_dict)} with offspeed data"
                )

            time.sleep(delay)

    except Exception as e:
        wlog.error(f"Worker {worker_id} error: {e}", exc_info=True)
    finally:
        driver_manager.close()
        wlog.info(f"Done. Found offspeed data for {patched} profiles.")


def main():
    parser = argparse.ArgumentParser(description="Patch missing offspeed stats")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()

    # Load existing CSV
    with open(ALL_PLAYERS_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)
    logger.info(f"Loaded {len(all_rows)} rows from CSV")

    # Find rows that need patching: have fastball data but no offspeed
    patched_set = load_checkpoint()
    needs_patch = []
    for row in all_rows:
        if row.get("link") in patched_set:
            continue
        has_fb = bool(row.get("fastball_velo_max") or row.get("fastball_velo_range"))
        has_offspeed = any(row.get(c) for c in OFFSPEED_COLS if not c.endswith("_date"))
        if has_fb and not has_offspeed:
            needs_patch.append(row)

    logger.info(f"{len(needs_patch)} profiles to check for offspeed data")
    logger.info(f"{len(patched_set)} already checked (checkpoint)")

    if not needs_patch:
        logger.info("Nothing to patch.")
        return

    # Distribute across workers
    num_workers = min(args.workers, len(needs_patch))
    chunks = [[] for _ in range(num_workers)]
    for i, row in enumerate(needs_patch):
        chunks[i % num_workers].append(row)

    # Shared state
    results_lock = threading.Lock()
    results_dict = {}
    patched_lock = threading.Lock()
    progress = {"done": 0, "total": len(needs_patch)}
    progress_lock = threading.Lock()
    stop_event = threading.Event()
    headless = not args.visible

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for wid in range(num_workers):
                futures.append(executor.submit(
                    worker_patch, wid, chunks[wid], args.delay, headless,
                    results_lock, results_dict, patched_set, patched_lock,
                    progress, progress_lock, stop_event,
                ))
            for f in futures:
                f.result()
    except KeyboardInterrupt:
        logger.info("Interrupted! Stopping workers...")
        stop_event.set()
    finally:
        save_checkpoint(patched_set)

    logger.info(f"Found offspeed data for {len(results_dict)} profiles")

    if not results_dict:
        logger.info("No offspeed data found. CSV unchanged.")
        return

    # Patch the CSV
    patched_count = 0
    for row in all_rows:
        url = row.get("link", "")
        if url in results_dict:
            for col, val in results_dict[url].items():
                row[col] = val
            patched_count += 1

    # Write patched CSV
    with open(PATCHED_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"Patched {patched_count} rows. Saved to {PATCHED_CSV_PATH}")
    logger.info(f"To use: rename {PATCHED_CSV_PATH} -> {ALL_PLAYERS_CSV_PATH}")


if __name__ == "__main__":
    main()
