"""Placeholder benchmark: proves that `mise run bench:<name>` reaches a script in bench/."""

import json
import time


def main() -> None:
    iterations = 1_000_000
    start = time.perf_counter()
    total = 0
    for value in range(iterations):
        total += value
    elapsed = time.perf_counter() - start
    print(json.dumps({"bench": "smoke", "iterations": iterations, "seconds": round(elapsed, 6)}))


if __name__ == "__main__":
    main()
