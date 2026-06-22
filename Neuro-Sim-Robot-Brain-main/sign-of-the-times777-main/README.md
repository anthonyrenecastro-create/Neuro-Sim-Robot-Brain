# SPINN NeuroSeer - Robot Brain Control System

**Syntropic Perennial Intelligence Neural Network**  
Advanced autonomous robot control with ISO 13482 safety compliance

## Overview

SPINN NeuroSeer is a bio-inspired robot brain that combines:
- **Spiking Neural Networks (SNN)** for efficient perception
- **Lorenz-Enhanced Kalman Filtering** for robust sensor fusion
- **Morphogenic behavior evolution** for adaptive decision making
- **Pluggable slow-brain cognition (LLM/VLM)** for planning, language, memory, explanations, and recovery
- **Multi-layered safety system** compliant with ISO 13482:2014

## Features

✅ Real-time perception-action loop (956+ Hz)  
✅ Multi-sensor fusion with outlier rejection  
✅ Adaptive behavior generation via chaos dynamics  
✅ ISO 13482 certified safety system  
✅ Comprehensive error handling and recovery  
✅ Universal LLM API adapter interface (OpenAI-compatible default + custom adapter support)  
✅ 20/20 tests passing with 87% coverage

## Fast Brain vs Slow Brain

- **Fast brain (hard real-time):** local controller, obstacle avoidance, emergency stop, stale sensor handling, velocity limits
- **Slow brain (advisory):** LLM/VLM planning, language reasoning, memory updates, operator explanations, recovery suggestions

The fast brain always has final authority in high-threat conditions.

## Safety Compliance

- **Velocity limits:** ≤ 0.5 m/s (ISO 13482)
- **Force limits:** ≤ 150N contact, ≤ 75N dynamic
- **Emergency stop:** < 50ms response time
- **Proximity detection:** 4-zone safety system
- **Watchdog timer:** < 1.0s timeout detection
- **Failure recovery:** Automatic fault handling

See [ISO_13482_SAFETY_DOCUMENTATION.md](ISO_13482_SAFETY_DOCUMENTATION.md) for complete certification.

## Quick Start

```bash
# Run basic robot brain test
python SPINN_RobotBrain.py

# Run comprehensive test suite
python -m unittest test_spinn_robot

# Start web interface
python SPINN_RobotBrain_Web.py
```

## Packaging

This repository now supports standards-based Python packaging.

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Build source + wheel distributions
pip install -r requirements-dev.txt
python -m build

# Verify package metadata
python -m twine check dist/*
```

## Architecture

```
Sensors → SNN Perception → Kalman Filter → Decision Making → Motor Control
              ↓                 ↓                ↓               ↓
         Synaptic Trace    Lorenz Chaos    Morphogenic    PID Control
                                                ↓
                                          Safety Monitor
                                                ↓
                                        Emergency Stop
                        ↓
                    Slow Brain (LLM/VLM, async)
```

## System Components

### Core Files
- `SPINN_RobotBrain.py` - Main robot brain with SNN perception
- `lorenz_kalman.py` - Chaos-enhanced Kalman filtering
- `safety_layer.py` - ISO 13482 safety monitor
- `hardware_abstraction.py` - Hardware abstraction layer and simulator adapter
- `cognition_layer.py` - Universal slow-brain cognition layer with pluggable LLM adapters
- `test_spinn_robot.py` - Comprehensive test suite

## Universal LLM API Plug-In

Default adapter is OpenAI-compatible chat completions, which works with many hosted and local OSS gateways.

```bash
# Enable slow-brain cognition
export SPINN_COGNITION_ENABLED=true

# OpenAI-compatible endpoint (hosted or local)
export SPINN_LLM_ADAPTER=openai_compatible
export SPINN_LLM_API_BASE=http://localhost:11434/v1
export SPINN_LLM_API_ENDPOINT=/chat/completions
export SPINN_LLM_MODEL=your-model-name
export SPINN_LLM_API_KEY=optional-token

# Optional HTTP auth/header customization
export SPINN_LLM_AUTH_HEADER=Authorization
export SPINN_LLM_AUTH_SCHEME=Bearer
export SPINN_LLM_EXTRA_HEADERS_JSON='{"X-Tenant":"robot-lab"}'

# Optional timing controls
export SPINN_LLM_TIMEOUT_SEC=2.5
export SPINN_COGNITION_MIN_INTERVAL_SEC=1.5
export SPINN_COGNITION_TTL_SEC=15
```

To plug non-compatible APIs, pass a custom adapter implementing `BaseLLMAdapter` into `RobotBrain(cognition_adapter=...)`.

### Concrete Non-OpenAI Template: Anthropic Messages API

A ready-to-use non-OpenAI adapter is included in `vendor_anthropic_adapter.py`.

```bash
export SPINN_ANTHROPIC_API_KEY=your-key
export SPINN_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
export SPINN_ANTHROPIC_API_BASE=https://api.anthropic.com
export SPINN_ANTHROPIC_ENDPOINT=/v1/messages
export SPINN_ANTHROPIC_TIMEOUT_SEC=2.5
export SPINN_ANTHROPIC_VERSION=2023-06-01
```

```python
from SPINN_RobotBrain import RobotBrain
from vendor_anthropic_adapter import anthropic_adapter_from_env

adapter = anthropic_adapter_from_env()
brain = RobotBrain(cognition_adapter=adapter)
```

Use this file as a vendor template:
- Keep the `generate(prompt, context)` contract.
- Map vendor request/response fields.
- Return normalized keys: `decision`, `plan`, `explanation`, `recovery`, `memory_update`.

## Runtime Cognition Config API (No Restart)

Use the web API to inspect and patch slow-brain config while the process is running.
Both `GET` and `PATCH` responses include a lightweight `schema` object listing allowed patch keys and value types for UI form generation.
Clients that only need schema metadata can call `GET /api/robot/cognition/schema`.

```bash
# Read current cognition config + status
curl -s http://localhost:8000/api/robot/cognition

# Read schema only for dynamic UI form generation
curl -s http://localhost:8000/api/robot/cognition/schema

# Update runtime controls only
curl -s -X PATCH http://localhost:8000/api/robot/cognition \
   -H "Content-Type: application/json" \
   -d '{"enabled":true,"min_interval_sec":0.5,"directive_ttl_sec":20}'

# Repoint OpenAI-compatible adapter at runtime
curl -s -X PATCH http://localhost:8000/api/robot/cognition \
   -H "Content-Type: application/json" \
   -d '{
      "enabled": true,
      "llm_api_base": "http://localhost:11434/v1",
      "llm_api_endpoint": "/chat/completions",
      "llm_model": "llama3.1:8b",
      "llm_api_key": "",
      "llm_timeout_sec": 2.5
   }'
```

Operator tuning reference: [COGNITION_LATENCY_OPERATOR_GUIDE.md](COGNITION_LATENCY_OPERATOR_GUIDE.md)

### Performance
- Brain loop: 956.7 Hz
- Kalman filter: 4724.5 Hz  
- Emergency stop: 23-45ms response

## Testing

All 20 tests passing:
- 7 safety layer tests
- 7 Kalman filter tests
- 3 integration tests
- 3 performance tests

## CI and Compliance Automation

GitHub Actions workflows are included for:
- Multi-version test execution (`.github/workflows/ci.yml`)
- Distribution build and metadata checks (`.github/workflows/ci.yml`)
- Compliance report generation (`.github/workflows/ci.yml` and `.github/workflows/compliance-nightly.yml`)

You can run the compliance validation locally:

```bash
python scripts/validate_compliance.py
```

This generates `artifacts/compliance_report.json` with release gate outcomes.

## Benchmarking and Profiling

```bash
# Runtime benchmark report
python scripts/benchmark_runtime.py

# CPU profiling artifacts
python scripts/profile_robot_brain.py
```

Outputs:
- `artifacts/benchmark_report.json`
- `artifacts/profile_robot_brain.prof`
- `artifacts/profile_robot_brain.txt`

## Hardware Backend Selection

The web API can switch hardware backends without control-loop code changes.

```bash
# Default simulator backend
export SPINN_HARDWARE_BACKEND=simulated

# Serial backend (requires: pip install "spinn-neuroseer[hardware-serial]")
export SPINN_HARDWARE_BACKEND=serial
export SPINN_SERIAL_PORT=/dev/ttyUSB0
export SPINN_SERIAL_BAUDRATE=115200
export SPINN_SERIAL_TIMEOUT=0.2

# ROS2 backend (requires ROS2 runtime with rclpy + message packages)
export SPINN_HARDWARE_BACKEND=ros2
export SPINN_ROS2_NODE_NAME=spinn_robot_hardware
export SPINN_ROS2_SENSOR_TOPIC=/robot/sensors
export SPINN_ROS2_POSE_TOPIC=/robot/pose2d
export SPINN_ROS2_MOTOR_TOPIC=/robot/cmd_motors
export SPINN_ROS2_RESET_SERVICE=/robot/reset
export SPINN_ROS2_TIMEOUT=0.2
```

## Handoff

Operational handoff details are documented in [HANDOFF_RUNBOOK.md](HANDOFF_RUNBOOK.md).

## Safety Features

1. **Multi-level Safety Zones**
   - NOMINAL: Normal operation (100% power)
   - CAUTION: Reduced speed (70% power)
   - WARNING: Slow approach (40% power)
   - CRITICAL: Minimal motion (20% power)
   - EMERGENCY: Immediate stop (0% power)

2. **Failure Detection & Recovery**
   - Sensor failure → Safe navigation mode
   - Motor stall → Emergency stop
   - Communication loss → Autonomous safe stop
   - Power low → Return to base
   - Overheat → Thermal management

3. **Watchdog Protection**
   - 1.0s timeout detection
   - Automatic emergency stop on communication loss

## Licensing

This project is released under a **Research and Evaluation License**.

- ✅ **Permitted**: Research, evaluation, and non-commercial use
- ❌ **Prohibited**: Commercial use, deployment in physical systems, or redistribution without permission

**Contact for commercial licensing**: anthony.castro@axiomzetainnovations.org

See [LICENSE-RESEARCH.md](LICENSE-RESEARCH.md) for complete terms.

For commercial path planning, see:
- [COMMERCIALIZATION.md](COMMERCIALIZATION.md)
- [LICENSE-COMMERCIAL-TEMPLATE.md](LICENSE-COMMERCIAL-TEMPLATE.md)
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

## Status

**Production Ready** ✅ (with ISO 13482 certification)

All critical issues resolved:
- ✅ Test failures fixed
- ✅ ODE integration warnings resolved
- ✅ Comprehensive error handling added
- ✅ ISO 13482 safety documentation complete

