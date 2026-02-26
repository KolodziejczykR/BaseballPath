import argparse
import asyncio
import time

import httpx


def _sample_payload(use_llm_reasoning: bool):
    return {
        "user_preferences": {
            "user_state": "CA",
            "preferred_states": ["CA"],
            "must_have_preferences": ["preferred_states"],
        },
        "player_info": {
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "exit_velo_max": 90.0,
            "sixty_time": 7.0,
            "inf_velo": 80.0,
            "throwing_hand": "R",
            "hitting_handedness": "R",
            "region": "West",
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.7,
                "d1_prediction": True,
                "confidence": "High",
                "model_version": "v1",
            }
        },
        "use_llm_reasoning": use_llm_reasoning,
    }


async def _worker(client: httpx.AsyncClient, url: str, payload: dict, results: list):
    start = time.time()
    resp = await client.post(url, json=payload, timeout=60)
    elapsed = time.time() - start
    results.append((resp.status_code, elapsed))


async def run(url: str, total: int, concurrency: int, use_llm_reasoning: bool):
    results = []
    payload = _sample_payload(use_llm_reasoning)

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(concurrency)

        async def _bounded():
            async with sem:
                await _worker(client, url, payload, results)

        tasks = [asyncio.create_task(_bounded()) for _ in range(total)]
        await asyncio.gather(*tasks)

    latencies = sorted(r[1] for r in results)
    if latencies:
        p50 = latencies[int(0.50 * (len(latencies) - 1))]
        p95 = latencies[int(0.95 * (len(latencies) - 1))]
    else:
        p50 = p95 = 0.0

    codes = {}
    for code, _ in results:
        codes[code] = codes.get(code, 0) + 1

    print(f"Total requests: {total}")
    print(f"Concurrency: {concurrency}")
    print(f"Status codes: {codes}")
    print(f"P50 latency: {p50:.2f}s")
    print(f"P95 latency: {p95:.2f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/preferences/filter")
    parser.add_argument("--total", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(args.url, args.total, args.concurrency, args.use_llm))


if __name__ == "__main__":
    main()
