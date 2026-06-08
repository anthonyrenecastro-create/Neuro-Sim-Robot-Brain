#!/usr/bin/env python3
"""Benchmark runtime throughput and control-loop timing."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SPINN_RobotBrain import RobotBrain
from lorenz_kalman import LorenzEnhancedKalmanFilter
from hardware_abstraction import create_hardware_adapter


def benchmark_brain(iterations: int) -> Dict[str, Any]:
    brain = RobotBrain()
    hardware = create_hardware_adapter("simulated")

    start = time.perf_counter()
    for _ in range(iterations):
        sensors = hardware.get_sensors()
        perception = brain.perceive(sensors)
        decision = brain.think(perception)
        action = brain.act(decision)
        hardware.set_motors(action)
    elapsed = time.perf_counter() - start

    hardware.close()
    return {
        "iterations": iterations,
        "elapsed_sec": round(elapsed, 6),
        "hz": round(iterations / max(elapsed, 1e-9), 2),
    }


def benchmark_kalman(iterations: int) -> Dict[str, Any]:
    kf = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)

    start = time.perf_counter()
    for _ in range(iterations):
        kf.predict(0.01)
        kf.update(np.random.rand(2))
    elapsed = time.perf_counter() - start

    return {
        "iterations": iterations,
        "elapsed_sec": round(elapsed, 6),
        "hz": round(iterations / max(elapsed, 1e-9), 2),
    }


def benchmark_loop_timing(duration_sec: float, hz: float) -> Dict[str, Any]:
    brain = RobotBrain()
    hardware = create_hardware_adapter("simulated")

    started = brain.start(
        sensor_callback=hardware.get_sensors,
        motor_callback=hardware.set_motors,
        hz=hz,
    )
    if not started:
        raise RuntimeError("Failed to start robot brain loop")

    wall_start = time.perf_counter()
    time.sleep(duration_sec)
    wall_elapsed = time.perf_counter() - wall_start
    brain.stop(timeout=3.0)

    status = brain.get_status()
    loops = int(status.get("total_loops", 0))
    cadence_hz = loops / max(wall_elapsed, 1e-9)
    processing_hz = float(status.get("loop_frequency_hz", 0.0))

    hardware.close()
    return {
        "target_hz": hz,
        "duration_sec": round(wall_elapsed, 6),
        "loops": loops,
        "cadence_hz": round(cadence_hz, 2),
        "processing_hz": round(processing_hz, 2),
        "hz_error_pct": round((cadence_hz - hz) / max(hz, 1e-9) * 100.0, 2),
    }


def benchmark_hardware_calls(iterations: int) -> Dict[str, Any]:
    hardware = create_hardware_adapter("simulated")

    t0 = time.perf_counter()
    for _ in range(iterations):
        hardware.get_sensors()
    sensors_elapsed = time.perf_counter() - t0

    cmd = {"left_motor": 20.0, "right_motor": 20.0}
    t1 = time.perf_counter()
    for _ in range(iterations):
        hardware.set_motors(cmd)
    motors_elapsed = time.perf_counter() - t1

    hardware.close()
    return {
        "iterations": iterations,
        "get_sensors_avg_ms": round((sensors_elapsed / iterations) * 1000.0, 4),
        "set_motors_avg_ms": round((motors_elapsed / iterations) * 1000.0, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run runtime benchmark suite")
    parser.add_argument("--brain-iterations", type=int, default=300)
    parser.add_argument("--kalman-iterations", type=int, default=3000)
    parser.add_argument("--hardware-iterations", type=int, default=1000)
    parser.add_argument("--loop-duration", type=float, default=2.0)
    parser.add_argument("--loop-hz", type=float, default=20.0)
    parser.add_argument(
        "--report-path",
        default="artifacts/benchmark_report.json",
        help="Path to JSON benchmark report",
    )
    args = parser.parse_args()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brain": benchmark_brain(args.brain_iterations),
        "kalman": benchmark_kalman(args.kalman_iterations),
        "loop_timing": benchmark_loop_timing(args.loop_duration, args.loop_hz),
        "hardware": benchmark_hardware_calls(args.hardware_iterations),
    }

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Benchmark report written to: {report_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
