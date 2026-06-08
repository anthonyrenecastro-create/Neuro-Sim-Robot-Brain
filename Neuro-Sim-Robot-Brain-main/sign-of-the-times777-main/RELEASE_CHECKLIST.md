# Release Checklist

## Pre-release

- [ ] `python -m unittest test_spinn_robot -v`
- [ ] `python scripts/validate_compliance.py`
- [ ] `python -m build`
- [ ] `python -m twine check dist/*`

## Evidence Bundle

- [ ] Archive `artifacts/compliance_report.json`
- [ ] Confirm `ISO_13482_SAFETY_DOCUMENTATION.md` reflects current release
- [ ] Record CI workflow run IDs

## Commercial Readiness

- [ ] Commercial license terms executed
- [ ] Deployment constraints documented
- [ ] Customer safety obligations documented
