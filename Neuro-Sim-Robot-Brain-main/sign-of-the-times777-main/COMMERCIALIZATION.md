# Commercialization Path

This repository ships under a research and evaluation license by default. Use the steps below to move cleanly toward commercial release readiness.

## 1. License Transition Gate

1. Keep non-commercial usage under `LICENSE-RESEARCH.md`.
2. For commercial intent, execute a signed commercial agreement before production deployment.
3. Use `LICENSE-COMMERCIAL-TEMPLATE.md` as the legal baseline for drafting terms with counsel.

## 2. Technical Release Gate

Run the required quality gates:

```bash
python -m unittest test_spinn_robot -v
python scripts/validate_compliance.py
python -m build
python -m twine check dist/*
```

Required outcomes:
- All tests pass.
- `artifacts/compliance_report.json` is generated with `"release_ready": true`.
- Build artifacts (`sdist` and wheel) pass metadata checks.

## 3. Compliance Evidence Package

For each release candidate, archive:
- `artifacts/compliance_report.json`
- `ISO_13482_SAFETY_DOCUMENTATION.md`
- CI run URLs for `CI` and `Compliance Nightly`
- Release notes documenting safety-impacting changes

## 4. Commercial Distribution Controls

1. Tag a release only after gates pass.
2. Publish signed artifacts from `dist/`.
3. Include contractual constraints and support boundaries in customer-facing documentation.

## 5. Governance Checklist

- Versioned risk assessment is current.
- Safety constraints and limits are unchanged or re-validated.
- Emergency stop behavior remains within threshold.
- Performance gates continue to pass on supported Python versions.

## Legal Notice

This document is an engineering process guide, not legal advice. Final license language and compliance obligations should be approved by qualified legal counsel and safety assessors.
