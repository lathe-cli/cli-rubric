# CLI Rubric

Open, reproducible CLI experience evaluation for humans and AI agents.

CLI Rubric is an open-source project for measuring whether a command-line
interface is merely usable, genuinely good, or preferred in repeated use.
Human experience and agent experience are evaluated separately. They are never
merged into one total score.

> [!IMPORTANT]
> CLI Rubric is in its founding phase. There is no official rubric, score,
> badge, certification, or leaderboard yet. Any result produced before a
> validated rubric release must be labeled experimental.

## Founding documents

- [Vision](docs/VISION.md)
- [愿景（中文）](docs/VISION.zh-CN.md)

## Founding principles

- Evidence before scores.
- Human Score and Agent Score stay separate.
- Every official result is versioned, inspectable, and reproducible.
- The same public rules apply to Lathe and every other CLI.
- Improving a CLI against the published rubric is the intended outcome.
- Credibility is earned through validation and independent reproduction, not
  declared by the project.

## Current scope

The repository currently defines the project's public commitments. The scoring
method, reference implementation, delivery form, governance process, and first
validated rubric will be designed in public.

No implementation language or packaging form has been selected. CLI Rubric may
eventually ship as a CLI, library, CI integration, plugin, or a combination of
these, but the measurement method comes first.

## License

[MIT](LICENSE)
