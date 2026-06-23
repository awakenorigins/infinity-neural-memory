## What & why

<!-- Brief description. Link the issue: Closes #___ -->

## Checklist (the design law)

- [ ] `make verify` passes (21/21, exit 0)
- [ ] `make test` passes
- [ ] New behavior has a new test (no claim without a passing test)
- [ ] No phantom API — every referenced module/class exists in the shipped package
- [ ] Anything touching a write path goes through `Redactor` + respects `AdmissionGate`
- [ ] Stubs are labeled as stubs (no fake success)
- [ ] `CHANGELOG.md` updated under *Unreleased*
- [ ] Docs/README/SKILL.md updated if behavior changed
