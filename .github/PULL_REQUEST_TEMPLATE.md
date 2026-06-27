## Summary

<!-- What does this PR change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] New agent
- [ ] New dataset / connector
- [ ] Refactor / infra
- [ ] Docs

## Checklist

- [ ] `make lint` passes (ruff + mypy + eslint)
- [ ] `make test` passes
- [ ] If ML changed, model metric thresholds in `backend/tests/model/` still pass
- [ ] If `DecisionReport`/`AgentState` schemas changed, the change is justified below
- [ ] Docs updated (README / `docs/*`) where relevant
- [ ] No secrets committed; runs offline with `VECTIS_LLM_PROVIDER=mock`

## Explainability impact

<!-- Does this affect how AI outputs are explained or how the Critic validates them? -->
