#!/usr/bin/env python3
"""Profile SPINN robot brain hotspots using cProfile."""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SPINN_RobotBrain import RobotBrain
from hardware_abstraction import create_hardware_adapter


def run_workload(iterations: int) -> None:
    brain = RobotBrain()
    hardware = create_hardware_adapter("simulated")

    for _ in range(iterations):
        sensors = hardware.get_sensors()
        perception = brain.perceive(sensors)
        decision = brain.think(perception)
        action = brain.act(decision)
        hardware.set_motors(action)

    hardware.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile robot brain runtime")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--profile-path", default="artifacts/profile_robot_brain.prof")
    parser.add_argument("--summary-path", default="artifacts/profile_robot_brain.txt")
    args = parser.parse_args()

    profile_path = Path(args.profile_path)
    summary_path = Path(args.summary_path)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    profiler = cProfile.Profile()
    profiler.enable()
    run_workload(args.iterations)
    profiler.disable()
    profiler.dump_stats(str(profile_path))

    stats = pstats.Stats(profiler)
    stats.sort_stats("cumtime")

    with summary_path.open("w", encoding="utf-8") as f:
        stats.stream = f
        stats.print_stats(args.top)

    print(f"Profile binary written to: {profile_path}")
    print(f"Profile summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
