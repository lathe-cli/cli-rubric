# Three-CLI pilot v0

This is an experimental, unscored rehearsal for `gh`, `difyctl`, and
`awirectl`. It is not a general runner or an official CLI comparison.

The runner creates disposable fixtures: a private GitHub repository, a
temporary Dify config directory, and an Awire channel. Run it only with
accounts where those mutations are allowed. Cleanup targets only resources
created by the run.

```sh
uv run pilots/three-cli-v0/run.py --self-check
uv run pilots/three-cli-v0/run.py
```

A passing run means the protocol completed and every fixture was absent after
cleanup. It does not produce a score.

The accepted rehearsal is
[`three-cli-20260804T043135Z-7e87`](results/three-cli-20260804T043135Z-7e87/summary.json).
