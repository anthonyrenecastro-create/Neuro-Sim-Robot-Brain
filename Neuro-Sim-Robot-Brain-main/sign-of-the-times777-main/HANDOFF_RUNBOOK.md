# Handoff Runbook

This runbook is the operational handoff for SPINN NeuroSeer after architecture cleanup, HAL introduction, and production loop hardening.

## 1. Current Architecture

Control stack:
- `SPINN_RobotBrain.py`: perception-think-act loop and timing/thread lifecycle
- `safety_layer.py`: ISO 13482 constraints and fail-safe enforcement
- `lorenz_kalman.py`: sensor fusion and uncertainty estimation
- `hardware_abstraction.py`: backend-agnostic hardware interface + adapters
- `SPINN_RobotBrain_Web.py`: API/runtime orchestration with backend factory selection

Hardware adapters (factory path):
- `simulated` -> `SimulatedRobotHardware`
- `serial` -> `SerialJsonRobotHardware`
- `ros2` -> `Ros2RobotHardware`

## 2. Backend Selection

Web runtime reads environment variables during `/api/robot/init`.

Default simulator:
```bash
export SPINN_HARDWARE_BACKEND=simulated
```

Serial backend:
```bash
export SPINN_HARDWARE_BACKEND=serial
export SPINN_SERIAL_PORT=/dev/ttyUSB0
export SPINN_SERIAL_BAUDRATE=115200
export SPINN_SERIAL_TIMEOUT=0.2
```

ROS2 backend:
```bash
export SPINN_HARDWARE_BACKEND=ros2
export SPINN_ROS2_NODE_NAME=spinn_robot_hardware
export SPINN_ROS2_SENSOR_TOPIC=/robot/sensors
export SPINN_ROS2_POSE_TOPIC=/robot/pose2d
export SPINN_ROS2_MOTOR_TOPIC=/robot/cmd_motors
export SPINN_ROS2_RESET_SERVICE=/robot/reset
export SPINN_ROS2_TIMEOUT=0.2
```

## 3. Real Hardware Protocol Contracts

### Serial JSON contract
Request/response is newline-delimited JSON.
- `{"cmd":"get_sensors"}` -> `{"status":"ok","sensors":[f,l,r]}`
- `{"cmd":"set_motors","left_motor":X,"right_motor":Y}` -> `{"status":"ok","pose":{"x":..,"y":..,"theta":..}}`
- `{"cmd":"get_pose"}` -> `{"status":"ok","pose":{"x":..,"y":..,"theta":..}}`
- `{"cmd":"reset"}` -> `{"status":"ok"}`

### ROS2 contract
Topics/services expected by `Ros2RobotHardware`:
- Sensor subscription (`Float32MultiArray`): `/robot/sensors`
- Pose subscription (`geometry_msgs/Pose2D`): `/robot/pose2d`
- Motor command publisher (`Float32MultiArray [left,right]`): `/robot/cmd_motors`
- Reset service (`std_srvs/Trigger`): `/robot/reset`

## 4. Verification Commands

Core tests:
```bash
python -m unittest test_spinn_robot -v
```

Compliance:
```bash
python scripts/validate_compliance.py
```

Benchmark:
```bash
python scripts/benchmark_runtime.py
```

Profile:
```bash
python scripts/profile_robot_brain.py
```

Artifacts:
- `artifacts/compliance_report.json`
- `artifacts/benchmark_report.json`
- `artifacts/profile_robot_brain.prof`
- `artifacts/profile_robot_brain.txt`

## 5. CI Expectations

Workflow jobs:
- `test`
- `build`
- `compliance`
- `benchmark-profile`

All jobs should pass before release/tagging.

## 6. Production Handoff Checklist

- Confirm backend env vars in deployment manifest.
- Validate emergency stop path on target hardware.
- Verify watchdog behavior under comms interruption.
- Capture and archive benchmark/profile artifacts per release.
- Record hardware firmware version paired with software release.
- Keep safety and license docs aligned with deployment scope.

## 7. Known Constraints

- ROS2 adapter requires ROS2 runtime and message/service packages.
- Serial adapter assumes stable line-delimited JSON framing.
- Simulator remains the reference backend for CI and deterministic tests.
