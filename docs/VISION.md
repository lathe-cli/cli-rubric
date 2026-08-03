# CLI Rubric Vision

> Open, reproducible CLI experience evaluation for humans and AI agents.

## Status

This document sets the project's direction. It is not a scoring specification.

CLI Rubric has no official score, badge, certification, or leaderboard until a
versioned rubric has been tested and published. Earlier results must be marked
experimental.

## Purpose

A CLI can expose the right operations and still be hard to discover, unsafe to
run, difficult to recover, or unpleasant to use.

CLI Rubric measures two different interfaces:

- the interface between a CLI and a human;
- the interface between a CLI and an AI agent.

These are related but not interchangeable. A CLI may serve one well and fail
the other.

## Principles

1. **Two scores, never one total.** Human Score and Agent Score stay separate.
2. **Evidence before scores.** Every score must link to observations and raw
   results.
3. **Context is part of the result.** Tasks, users, agents, platforms, and
   budgets must be declared.
4. **The method is public.** Criteria, weights, gates, fixtures, and known
   limitations are inspectable.
5. **The same rules apply to comparable CLIs.** Lathe receives no exception.
6. **Improving against the rubric is encouraged.** Better real outcomes are the
   purpose of the project.
7. **Credibility is earned.** Source code and citations do not replace
   validation or independent reproduction.

## What a score means

A CLI Rubric result applies only to the declared:

- CLI artifact and version;
- task pack;
- evaluation profile;
- operating system, shell, terminal, locale, and environment;
- human cohort or agent panel;
- available documentation, network, credentials, and fixtures;
- time, token, tool-call, and other budgets;
- rubric, grader, and runner versions.

There is no context-free universal CLI score. Results are directly comparable
only when these inputs are materially compatible.

## Human Score

Human Score measures whether specified people can complete specified tasks
effectively, efficiently, safely, and with confidence.

The rubric should cover:

- onboarding and discovery;
- task completion and correctness;
- time, effort, and avoidable steps;
- command and option clarity;
- feedback and output readability;
- error prevention, diagnosis, and recovery;
- consistency and transfer of learning;
- control, reversibility, and safety;
- satisfaction and repeated-use preference.

Static checks are supporting evidence, not a Human Score. A valid score needs
task observations and, where appropriate, controlled comparisons and validated
questionnaires. Participant profile, study design, exclusions, and uncertainty
must be reported.

## Agent Score

Agent Score measures whether specified agents can complete specified tasks
through the CLI reliably, efficiently, and without unsupported guesses.

The rubric should cover:

- capability and command discovery;
- intent-to-invocation correctness;
- parameter, schema, and authentication clarity;
- machine-readable output and stable error semantics;
- task correctness;
- invalid-action detection and repair;
- determinism;
- tool calls, tokens, retries, time, and context use;
- non-interactive behavior;
- preview, idempotency, reversibility, and safe failure.

Agent quality can hide or exaggerate interface quality. Comparisons must
therefore hold tasks, prompts, budgets, and harness behavior fixed; repeat
stochastic trials; disclose exact models and agent versions; and separate CLI,
agent, backend, and environment failures.

Broad claims require a representative agent panel. A result from one model is
scoped to that model.

Deterministic graders are preferred. An LLM judge is allowed only when direct
grading is impractical. Its prompt, model, raw output, calibration, agreement
with qualified human labels, and known failure modes must be published.

## Score bands

Each track has its own 0–100 score:

| Range | Label | Meaning |
| --- | --- | --- |
| 0–59 | Unusable | Core tasks are not reliably completed. |
| 60–79 | Usable | Core tasks work, but material friction remains. |
| 80–89 | Good | Normal use is reliable, clear, and efficient. |
| 90–100 | Preferred | Repeated use shows strong, validated preference. |

For humans, preference is observed or reported by the target cohort. For
agents, preference means consistently better controlled outcomes or lower
interaction cost; it does not imply feelings.

These bands are provisional. They are not supplied by ISO or another external
authority. Before rubric v1, pilot data must test whether the boundaries
separate meaningful differences in outcomes.

## Scoring rules

Every top-level score must be decomposable into:

- dimension scores;
- individual measures;
- weights and transformations;
- gates and caps;
- raw evidence;
- missing or excluded data;
- uncertainty and trial counts.

Missing evidence is reported as `not evaluated`, not guessed or converted to
zero.

Critical failures cannot be averaged away. Data loss, false success, secret
exposure, or failure of a required core task may trigger a public gate or score
cap.

If uncertainty crosses a band boundary, the report must show that ambiguity.
Meaningless decimal precision is not allowed.

## Evidence bundle

Every official evaluation produces a portable evidence bundle containing:

- subject version, source, artifact digest, and installation method;
- rubric, profile, task pack, grader, and runner versions;
- environment and fixture manifests;
- sanitized commands, stdin, stdout, stderr, exit status, and state changes;
- timings, retries, resources, and failure classifications;
- human study details or agent configuration and trajectories;
- component scores, transformations, uncertainty, and limitations;
- integrity hashes.

Secrets and personal data must be removed or replaced with safe references.
Redaction and its effect on reproducibility must be disclosed. Covert telemetry
is not required.

Reports must state whether they are:

- experimental;
- repeatable by the original evaluator;
- independently reproduced;
- validated across different environments or cohorts.

## Fairness

CLI Rubric promises procedural fairness, not perfect objectivity:

- rules are public;
- comparable subjects receive the same treatment;
- observations and judgments are separated;
- subjective measures are labeled;
- conflicts and protocol deviations are disclosed;
- scoring changes are versioned;
- historical results keep their original method identifiers;
- corrections and appeals leave an audit trail.

CLI authors may optimize against every published criterion. Adding structured
output, correcting exit codes, improving help, reducing prompts, or making
failures recoverable is the intended outcome.

The method must still detect test-specific changes that do not improve broader
use. It may use diverse tasks, negative cases, parameterized fixtures,
sensitivity analysis, and transfer checks. There are no secret criteria or
hidden weights.

If a task instance is temporarily withheld, its policy, generation method,
access rules, and release schedule must be public.

## The Lathe conflict

CLI Rubric is hosted by `lathe-cli` and was started by people connected to
Lathe. That conflict must be visible.

- Lathe receives no private criteria, fixtures, weights, prompts, or exceptions.
- Lathe is evaluated from public artifacts under the released protocol.
- Lathe-specific features score only when they satisfy a general requirement
  available to every CLI.
- Poor Lathe results must be published as honestly as strong results.
- Evaluator, sponsor, and maintainer relationships are disclosed.
- A maintainer-produced Lathe report is not labeled independent.

No vendor may buy a score, suppress a valid result, or receive private advance
access.

## How the method earns credibility

Rubric v1 must demonstrate:

- **content validity:** the dimensions cover material CLI experience;
- **construct validity:** measures reflect the claimed quality, not shallow
  proxies;
- **criterion validity:** higher scores predict better external outcomes;
- **reliability:** repeats and qualified raters reach compatible conclusions;
- **robustness:** reasonable changes in tasks, weights, models, cohorts, and
  environments do not reverse the result without explanation;
- **uncertainty:** variation and limits on generalization are reported;
- **independent reproduction:** a party outside the project can reproduce the
  evidence and conclusion.

The project must distinguish performance on a fixed task pack from claims about
the wider population of possible tasks.

## Governance

Material scoring changes require a public proposal with rationale and evidence.

Rubrics, profiles, schemas, task packs, and graders are versioned. Historical
results are never silently rewritten under a new method. Corrections retain an
audit trail.

Governance must include conflict disclosure, recusal, review periods, appeals,
and a path for independent implementations. Evidence should be sufficient for
others to calculate alternative scorecards.

Only results that follow a released protocol may use its official CLI Rubric
designation.

## Initial scope

The first rubric targets non-full-screen CLIs that can run safely against
isolated fixtures.

It does not:

- rate the overall service or API behind a CLI;
- certify security, legal compliance, or production readiness;
- rate graphical interfaces, IDE extensions, or full-screen TUIs;
- rank incompatible CLI categories;
- replace human research with an LLM judge;
- treat a static checklist as complete experience evidence;
- select an implementation language or delivery form.

Security, accessibility, performance, and reliability matter when they affect
the declared experience, but CLI Rubric does not replace a specialist audit.

## Path to rubric v1

1. Define Human and Agent constructs, profiles, evidence schema, and safe
   execution rules.
2. Publish proposed dimensions, weights, gates, task packs, and validation plan
   before using pilot outcomes to tune them.
3. Pilot on diverse CLIs, including Lathe, non-Lathe tools, and deliberately
   weak reference interfaces.
4. Test reliability, validity, sensitivity, and the 60/80/90 boundaries before
   publishing rubric v1.

All pilot scores remain experimental.

## Success

CLI Rubric succeeds when:

- maintainers can reproduce and act on every finding;
- independent evaluators reach compatible conclusions;
- higher scores predict better human or agent task outcomes;
- improving a score improves real use;
- Lathe is treated like every comparable CLI.

The goal is not to maximize the number of scored projects. It is to make CLI
experience measurably better.

## References

These sources inform the method but do not endorse CLI Rubric. Released rubrics
must remain open and self-contained.

- [ISO 9241-11:2018 — Usability](https://www.iso.org/standard/63500.html)
- [ISO 9241-110:2020 — Interaction
  principles](https://www.iso.org/standard/75258.html)
- [ISO/IEC 25010:2023 — Product quality
  model](https://www.iso.org/standard/78176.html)
- [ISO/IEC 25022:2016 — Quality in
  use](https://www.iso.org/standard/35746.html)
- [The Open Group — Utility
  Conventions](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html)
- [Command Line Interface Guidelines](https://clig.dev/)
- [ACM Artifact Review and
  Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current)
- [NIST AI 800-2 — Automated Benchmark
  Evaluations](https://doi.org/10.6028/NIST.AI.800-2.ipd)
- [NIST AI 800-3 — Statistical Models for AI
  Evaluation](https://doi.org/10.6028/NIST.AI.800-3)
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)
- [Berkeley Function Calling
  Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard)
- [τ-bench](https://github.com/sierra-research/tau2-bench)
