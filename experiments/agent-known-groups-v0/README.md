# Agent Known-Groups Validation v0

This experiment qualifies a blind Agent evaluation path against the controlled
`degraded`, `neutral`, and `improved` resource-lifecycle variants.

Qualification results are disposable, unscored, and written under `.local/`.
They are not known-groups validation evidence.

The summary reports `harness_status` separately from `qualification_status`.
Only integrity failures invalidate and exclude a trial. Command or tool-call
overruns and malformed actor responses remain valid failed outcomes. Provider
token thresholds are cost metadata and do not change validity or outcome.

```sh
uv run experiments/agent-known-groups-v0/run.py --self-check
uv run experiments/agent-known-groups-v0/run.py --qualification --acknowledge-cost
uv run experiments/agent-known-groups-v0/score.py .local/agent-known-groups-v0/<run-id>/*.evidence.json
```

The formal run is a separate gate: three independent model families, ten
repetitions per model-task condition, all six tasks, all three variants, and
540 trials. It requires external protocol review, held-out material, and
explicit cost authorization.
