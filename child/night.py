from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from child.tools import moscow_now

MSK = ZoneInfo("Europe/Moscow")
DEADLINE = datetime(2026, 8, 18, 7, 20, tzinfo=MSK)
SEC_PER_STEP = 0.45
RESERVE_SEC = 120

# Recite often so a new world page does not eat Привет or print.
PLAN: tuple[tuple[str, ...], ...] = (
    ("train", "recite_all", "1000", "5e-5"),
    ("train", "world_school", "1400", "8e-5"),
    ("learn", "поучи мир в интернете", "800"),
    ("train", "recite_all", "900", "5e-5"),
    ("learn", "поучи python в интернете", "600"),
    ("train", "recite_all", "1000", "5e-5"),
    ("learn", "поучи english в интернете", "600"),
    ("train", "world_school", "1000", "7e-5"),
    ("train", "recite_all", "1200", "5e-5"),
)


def minutes_left(now: datetime | None = None) -> float:
    stamp = now or datetime.now(MSK)
    return (DEADLINE - stamp).total_seconds() / 60.0


def still_night(now: datetime | None = None, reserve_min: float = 2.0) -> bool:
    return minutes_left(now) > reserve_min


def fit_steps(wanted: int, now: datetime | None = None) -> int:
    left = minutes_left(now) * 60.0 - RESERVE_SEC
    if left <= 0:
        return 0
    return max(0, min(wanted, int(left / SEC_PER_STEP)))


def _run(cmd: list[str]) -> int:
    print("night>", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def run_lesson(kind: str, *parts: str) -> int:
    if kind == "train":
        stage, steps, lr = parts
        fitted = fit_steps(int(steps))
        if fitted < 200:
            print(f"night> skip {stage}: only {fitted} steps fit before 07:20")
            return 0
        return _run(
            [
                sys.executable,
                "-u",
                "-m",
                "child.train",
                "--stage",
                stage,
                "--steps",
                str(fitted),
                "--lr",
                lr,
                "--skip-exam",
                "--sample-every",
                "0",
            ]
        )
    if kind == "learn":
        wish, steps = parts
        fitted = fit_steps(int(steps))
        if fitted < 200:
            print(f"night> skip learn {wish!r}: only {fitted} steps fit")
            return 0
        return _run(
            [
                sys.executable,
                "-u",
                "-m",
                "child.learn",
                "--wish",
                wish,
                "--web",
                "--steps",
                str(fitted),
                "--skip-exam",
                "--keep-inbox",
                "--sample-every",
                "0",
            ]
        )
    raise ValueError(f"unknown night lesson {kind!r}")


def run_until_morning() -> int:
    print(f"Night watch. Moscow now {moscow_now()}. Stop at 07:20.", flush=True)
    if not still_night():
        print("Morning already. No more lessons.")
        return 0
    queue = list(PLAN)
    extra = 0
    while still_night():
        if not queue:
            extra += 1
            queue.append(("train", "recite_all", "800", "5e-5"))
            if extra % 2 == 0:
                queue.append(("train", "world_school", "800", "6e-5"))
        kind, *parts = queue.pop(0)
        print(
            f"night> {kind} {parts}  left={minutes_left():.1f} min",
            flush=True,
        )
        code = run_lesson(kind, *parts)
        if code != 0:
            print(f"night> lesson failed with {code}, continue")
        if fit_steps(200) < 200:
            print("night> not enough time for another lesson")
            break
    print(f"Night ends. Moscow now {moscow_now()}.", flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Keep teaching the child until 07:20 Moscow time."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run only the next fitting lesson, then exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.once:
        if not still_night():
            print("Morning already.")
            return
        kind, *parts = PLAN[0]
        raise SystemExit(run_lesson(kind, *parts))
    raise SystemExit(run_until_morning())


if __name__ == "__main__":
    main()
