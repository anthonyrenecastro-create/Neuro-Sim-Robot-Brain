#!/usr/bin/env python3
"""Generate an auditable ISO 13482 compliance validation report."""

from __future__ import annotations

import argparse
import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Ensure repository root is importable when running from scripts/.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SPINN_RobotBrain import RobotBrain, RobotSimulator
from lorenz_kalman import LorenzEnhancedKalmanFilter
from safety_layer import ISO13482Compliance, SafetyConstraints, SafetyMonitor
import test_spinn_robot


BRAIN_MIN_HZ = 10.0
KALMAN_MIN_HZ = 100.0
ESTOP_MAX_MS = 100.0


def measure_brain_throughput(iterations: int = 100) -> float:
    """Measure robot brain perception-think-act throughput in Hz."""
    brain = RobotBrain()
    sim = RobotSimulator()

    start = time.time()
    for _ in range(iterations):
        sensors = sim.get_sensors()
        perception = brain.perceive(sensors)
        decision = brain.think(perception)
        brain.act(decision)
    elapsed = time.time() - start

    return iterations / max(elapsed, 1e-9)


def measure_kalman_throughput(iterations: int = 1000) -> float:
    """Measure Lorenz-enhanced Kalman predict/update throughput in Hz."""
    kf = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)

    start = time.time()
    for _ in range(iterations):
        kf.predict(0.01)
        measurement = np.random.rand(2)
        kf.update(measurement)
    elapsed = time.time() - start

    return iterations / max(elapsed, 1e-9)


def run_safety_test_suite() -> Dict[str, Any]:
    """Run the safety-focused unittest classes used for release gates."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(test_spinn_robot.TestSafetyLayer))
    suite.addTests(loader.loadTestsFromTestCase(test_spinn_robot.TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(test_spinn_robot.TestPerformance))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
    }


def build_report() -> Dict[str, Any]:
    """Build the compliance report with pass/fail gates."""
    constraints = SafetyConstraints()
    monitor = SafetyMonitor(constraints)

    iso_checks = ISO13482Compliance.check_compliance(constraints)
    brain_hz = measure_brain_throughput()
    kalman_hz = measure_kalman_throughput()
    estop_ms = monitor.simulate_emergency_stop_response()
    safety_tests = run_safety_test_suite()

    gates = {
        "iso_checklist_all_true": all(bool(v) for v in iso_checks.values()),
        "brain_throughput_hz": brain_hz >= BRAIN_MIN_HZ,
        "kalman_throughput_hz": kalman_hz >= KALMAN_MIN_HZ,
        "emergency_stop_response_ms": estop_ms is not None and estop_ms <= ESTOP_MAX_MS,
        "safety_test_suite": safety_tests["successful"],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "standard": "ISO 13482:2014",
        "gates": gates,
        "measurements": {
            "brain_throughput_hz": round(brain_hz, 2),
            "kalman_throughput_hz": round(kalman_hz, 2),
            "emergency_stop_response_ms": None if estop_ms is None else round(estop_ms, 3),
        },
        "thresholds": {
            "brain_min_hz": BRAIN_MIN_HZ,
            "kalman_min_hz": KALMAN_MIN_HZ,
            "emergency_stop_max_ms": ESTOP_MAX_MS,
        },
        "iso_checks": iso_checks,
        "safety_tests": safety_tests,
        "release_ready": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compliance and emit JSON report.")
    parser.add_argument(
        "--report-path",
        default="artifacts/compliance_report.json",
        help="Output path for the generated JSON report",
    )
    args = parser.parse_args()

    report = build_report()

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Compliance report written to: {report_path}")
    print(f"Release ready: {report['release_ready']}")

    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
