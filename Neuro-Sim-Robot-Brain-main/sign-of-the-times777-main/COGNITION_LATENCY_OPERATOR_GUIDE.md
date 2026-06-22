# Slow-Brain Latency Operator Guide

This guide helps operators tune slow-brain cognition quality while preserving fast-brain real-time safety.

## Core Rule

Fast brain always controls safety outcomes.
Slow-brain requests must be bounded so they never pressure safety-critical loops.

## Timing Model

Use these variables:
- Brain loop period: `T_loop = 1 / loop_hz`
- LLM request timeout: `T_llm = SPINN_LLM_TIMEOUT_SEC`
- Cognition cadence: `T_cog = SPINN_COGNITION_MIN_INTERVAL_SEC`
- Directive lifetime: `T_ttl = SPINN_COGNITION_TTL_SEC`

Recommended relationships:
- `T_llm >= p95 network+model latency`
- `T_cog >= T_llm` for low contention
- `T_ttl >= 5 * T_cog` so directives stay usable between updates
- Keep `T_llm <= 0.5 * watchdog_timeout` as a conservative guardrail

## Recommended Presets

Assume watchdog timeout is 1.0s.

### Safety-first profile
- Use when operating near people/obstacles or unstable networking.
- `SPINN_LLM_TIMEOUT_SEC=0.30`
- `SPINN_COGNITION_MIN_INTERVAL_SEC=1.50`
- `SPINN_COGNITION_TTL_SEC=8`
- Expected behavior: fewer slow-brain updates, minimal risk of stale guidance.

### Balanced profile
- Default for most environments.
- `SPINN_LLM_TIMEOUT_SEC=0.60`
- `SPINN_COGNITION_MIN_INTERVAL_SEC=1.20`
- `SPINN_COGNITION_TTL_SEC=12`
- Expected behavior: stable planning refresh with good safety margin.

### Quality-first profile
- Use for low-speed trials in controlled spaces.
- `SPINN_LLM_TIMEOUT_SEC=0.90`
- `SPINN_COGNITION_MIN_INTERVAL_SEC=1.00`
- `SPINN_COGNITION_TTL_SEC=15`
- Expected behavior: richer reasoning with tighter timing budget.

## Runtime Update Examples

Use runtime API to tune without restart.

```bash
# Safety-first
curl -s -X PATCH http://localhost:8000/api/robot/cognition \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"min_interval_sec":1.5,"directive_ttl_sec":8,"llm_timeout_sec":0.3}'

# Balanced
curl -s -X PATCH http://localhost:8000/api/robot/cognition \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"min_interval_sec":1.2,"directive_ttl_sec":12,"llm_timeout_sec":0.6}'

# Quality-first
curl -s -X PATCH http://localhost:8000/api/robot/cognition \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"min_interval_sec":1.0,"directive_ttl_sec":15,"llm_timeout_sec":0.9}'
```

## Commissioning Workflow

1. Start with Safety-first profile.
2. Run for 10-15 minutes and monitor:
   - safety transitions
   - emergency stop events
   - cognition failures and last_error
3. Increase quality one step at a time by reducing `min_interval_sec` or increasing `llm_timeout_sec`, not both at once.
4. If safety transitions or watchdog issues rise, revert one step immediately.

## Quick Decision Guide

- Frequent cognition timeouts: increase `SPINN_LLM_TIMEOUT_SEC` by 0.1-0.2s.
- Stale or outdated directives: lower `SPINN_COGNITION_MIN_INTERVAL_SEC` or raise `SPINN_COGNITION_TTL_SEC`.
- Excess network/model load: raise `SPINN_COGNITION_MIN_INTERVAL_SEC`.
- Any safety instability: switch to Safety-first preset and retest.

## Minimum Operator Checklist

- Cognition enabled only after robot init confirms healthy status.
- Runtime cognition config recorded before each run.
- Safety monitor and watchdog metrics reviewed after each run.
- Changes made in small increments and validated for at least 10 minutes.
