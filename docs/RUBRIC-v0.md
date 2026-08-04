# CLI Rubric v0

## Status

Rubric v0 is an experimental measurement design. It defines the constructs,
profiles, evidence contract, scoring proposal, and validation experiments that
must be tested before rubric v1.

It does not authorize an official score, badge, certification, or leaderboard.

## Decisions

- Human Score and Agent Score are separate.
- A score applies to one declared context, profile, and task pack.
- Task outcomes carry more weight than interface features or static checks.
- Missing required evidence produces no score.
- Critical failures can cap a score.
- The 90–100 band requires controlled preference evidence.
- Default results describe the fixed task pack, not all possible CLI tasks.
- All v0 results are experimental.

## Measurement claim

A CLI Rubric result has this form:

> Artifact X, evaluated under rubric R, profile P, and task pack T, achieved
> score S for track H or A.

Changing the artifact, rubric, profile, task pack, actor population, or material
environment creates a different result.

The profile states whether installation is a scored task or the subject is
preinstalled. A score must not imply that setup was evaluated when it was not.

[ISO 9241-11](https://www.iso.org/standard/63500.html) treats usability as an
outcome of use in a specified context. [ISO/IEC
25022](https://www.iso.org/standard/35746.html) defines quality-in-use measures
but explicitly leaves grade ranges to each product and context. The 60, 80, and
90 boundaries below are therefore CLI Rubric hypotheses, not ISO thresholds.

## Construct model

Each dimension is scored from 0 to 100. The track score is the weighted sum of
its dimensions before gates and rounding.

The weights are preregistered v0 hypotheses. They prioritize task outcomes and
are not inherited from an external standard or tuned against existing CLI
scores.

### Human Score

Human Score measures whether CLI-literate people in the declared cohort can
learn and complete representative tasks effectively, efficiently, safely, and
with confidence.

- **H1 — Task outcome (35%):** completion 60%; result correctness 40%.
- **H2 — Discovery and learning (15%):** correct first path 40%; assistance
  burden 30%; transfer to a related task 30%.
- **H3 — Interaction efficiency (15%):** active completion time 50%;
  avoidable interactions 50%.
- **H4 — Error handling and control (20%):** prevention and diagnostic
  actionability 35%; recovery success 40%; preview and reversibility 25%.
- **H5 — Confidence and reuse (15%):** confidence in the result 50%; intent
  to choose the CLI again 50%.

H5 records human judgment. It cannot replace observed task outcomes. A validated
questionnaire may be reported beside the score, but it does not become the
score by default.

### Agent Score

Agent Score measures whether declared agent systems can complete representative
tasks through the CLI reliably, efficiently, safely, and without unsupported
guesses.

- **A1 — Task outcome (40%):** completion 60%; result correctness 40%.
- **A2 — Discovery and invocation (20%):** capability selection 35%; first
  valid invocation 35%; unsupported guesses 30%.
- **A3 — Output and state interpretation (15%):** parse success 35%; outcome
  and error interpretation 40%; state verification 25%.
- **A4 — Recovery and safety (15%):** invalid-input repair 35%;
  partial-failure recovery 35%; safe change behavior 30%.
- **A5 — Interaction efficiency (10%):** tool calls 40%; CLI-to-agent
  context 30%; elapsed time 30%.

The model, agent, prompt, tool surface, and budget are part of the result. A
single-model result is not a general Agent Score.

### Static checks

Static checks may detect useful properties such as:

- standard help and version behavior;
- exit status and stdout/stderr separation;
- non-interactive operation;
- structured output;
- secret-safe diagnostics;
- preview or dry-run support.

They support task evidence and failure diagnosis. They do not independently
produce a Human or Agent Score.

## Measure contract

Every measure definition must declare:

- construct and dimension;
- task applicability;
- observation or derived value;
- normalization rule;
- direction, where higher always means better;
- task and trial weights;
- evidence references;
- missing-data rule;
- grader and rater requirements;
- known validity threats.

Task packs must mark core tasks before evaluation. They must also publish
deterministic graders where task correctness can be checked directly.

### Normalization

Each trial-level measure is normalized to the closed interval 0–1.

- Binary outcomes use 0 or 1.
- Partial correctness uses a deterministic grader result between 0 and 1.
- Anchored ratings use measure-specific 0–4 anchors and divide by 4.
- Ordered response items map their lowest and highest anchors to 0 and 1.
- Cost measures use a target and limit declared before subject evaluation.

For a cost value `x`, target `a`, and failure limit `b`, where `a < b`:

```text
1                         when x <= a
(b - x) / (b - a)         when a < x < b
0                         when x >= b
```

Targets and limits come from task constraints or published expert reference
runs. They are not tuned after seeing the evaluated subject's result.

### Aggregation

For each measure:

1. Average valid repetitions for each actor and task.
2. Average actors within each task.
3. Combine tasks using weights declared in the task pack.
4. Combine measures using the dimension weights above.
5. Combine dimensions using the track weights above.

This ordering prevents tasks with more repetitions from silently receiving more
weight.

The raw score is:

```text
raw = 100 * sum(dimension_weight * dimension_value)
```

The displayed score is the nearest integer after gates are applied. Internal
calculations retain full precision. A report must retain the raw score,
dimension values, contributions, trial counts, and uncertainty.

Required evidence is not imputed. If a required measure is absent or a major
protocol deviation invalidates it, the result is `unscored`. A task or measure
may be inapplicable only when the released profile declares that fact before
evaluation.

## Gates

Gates apply after the raw score is calculated.

### Evidence gate

No score is produced when required task, actor, environment, grader, or
measurement evidence is missing.

### Core-task gate

The final score is capped at 59 when either condition holds:

- weighted full completion across core tasks is below 60%; or
- a core task has zero successful trials across at least three valid trials.

### Critical-failure gate

The final score is capped at 59 when evidence attributes any confirmed event
below to the CLI:

- data loss outside the declared task outcome;
- success reported for a failed consequential operation;
- secret exposure in normal output, diagnostics, or logs;
- a destructive action executed without the control required by the profile.

The event and attribution must be reviewable. An actor, backend, harness, or
environment failure is not silently reassigned to the CLI.

### Preference gate

A raw score of 90 or more is capped at 89 unless preference is supported on
held-out tasks against at least one comparable alternative.

For humans:

- the lower bound of a 95% interval for paired choice is above 0.5; and
- core-task completion is not more than five percentage points worse.

For agents:

- the lower bound of a 95% interval for paired wins is above 0.5; and
- the win rule considers correctness before interaction cost; and
- critical-failure incidence is not worse.

The alternative, pairing, win rule, and non-inferiority margin must be declared
before the comparison. Without a viable comparator, the highest available band
is Good.

The comparator must be a credible current option for the same tasks, selected
before subject results are known. A deliberately degraded fixture cannot
support the Preferred band.

## Bands

| Score | Label | Interpretation |
| --- | --- | --- |
| 0–59 | Unusable | Use fails, is unreliable, or a critical gate fires. |
| 60–79 | Usable | Core tasks work with material friction. |
| 80–89 | Good | Use is reliable, clear, and recoverable. |
| 90–100 | Preferred | Good plus controlled preference evidence. |

An interval that crosses a boundary sets `band_status` to `borderline`. The
numeric score remains visible, but the report must name both plausible bands.

## Uncertainty and estimand

The default estimand is performance on the fixed released task pack.

- Human intervals resample participants, preserving each participant's task
  cluster.
- Agent intervals resample repetitions within each fixed model and task.
- Fixed task-pack intervals do not pretend that tasks were randomly sampled.

A broader claim about potential tasks requires a documented task population or
generator and an analysis that includes task variation. This distinction
follows [NIST AI
800-3](https://www.nist.gov/publications/expanding-ai-evaluation-toolbox-statistical-models),
which separates fixed-benchmark performance from generalized performance and
its additional uncertainty.

Every score reports a 95% interval, trial counts, exclusions, and the interval
method. The report must separate variation caused by tasks, people or models,
CLI nondeterminism, backends, and graders when the design permits.

The scoring function, including caps, is applied inside each resample. A
confirmed critical event that is not sampling-dependent applies to every
resample.

## Evaluation profiles

A profile freezes the conditions that can materially change a result. The
machine-readable contract is
[`schemas/v0/profile.schema.json`](../schemas/v0/profile.schema.json).

Every profile declares:

- track, claim, CLI class, capability domain, and risk;
- whether installation is in scope or the subject is preinstalled;
- rubric and task-pack references with SHA-256 digests;
- platforms, shell, locale, terminal mode, isolation, and network policy;
- documentation snapshot and evaluator assistance;
- time, command, token, tool-call, and cost budgets where applicable;
- actor cohort or agent panel;
- repetitions, task ordering, reset policy, and captured evidence;
- grader policy;
- fixture-only safety controls.

Profiles are immutable after release. A changed field creates a new profile
version.

### Human Core v0

`human-core-v0` is the first proposed Human profile.

- Participants are CLI-literate and subject-naive at the start.
- The study contains first-use and repeated-use phases.
- Bundled help and a frozen public-documentation snapshot are available.
- Evaluators may explain the task but may not suggest commands.
- Task order is counterbalanced.
- Every operation runs against isolated fixtures.
- The pilot minimum is 24 participants.
- Command history, task state, timing, observed assistance, and response items
  are captured with informed consent.

The minimum is a pilot target, not a claim of statistical power. Rubric v1
requires a power analysis based on v0 variance and effect estimates.

### Agent Core v0

`agent-core-v0` is the first proposed Agent profile.

- Trials start without subject-specific conversation history.
- The agent receives the same task intent and frozen documentation snapshot.
- Private hints, hidden schemas, and Lathe-specific tool integrations are
  prohibited.
- The shell tool surface and harness are fixed within a comparison.
- The panel includes at least three independently developed model families.
- Each model-task condition has at least ten valid repetitions.
- Model, provider, agent, harness, prompt, parameters, and budgets are recorded.
- Every operation runs non-interactively against isolated fixtures.

A second harness is used in the robustness experiment, not mixed into the core
profile score.

### Comparability

Direct score comparison requires identical:

- track and rubric digest;
- profile digest;
- task-pack digest;
- grader digest;
- actor cohort definition or agent panel;
- material environment and documentation policy.

Results with differences may still be reported side by side, but they are
marked `not directly comparable`. Incompatible CLI categories are not ranked.

## Evidence schema

The evidence contract is
[`schemas/v0/evidence.schema.json`](../schemas/v0/evidence.schema.json).

An evidence bundle separates:

1. **Observation:** commands, streams, exit status, duration, task state, and
   raw responses.
2. **Measurement:** normalized values linked to observations.
3. **Judgment:** failure attribution, anchored ratings, exclusions, and
   protocol deviations.
4. **Projection:** dimensions, raw score, gates, final score, band, and
   uncertainty.

The manifest records:

- exact subject artifact and installation method;
- rubric, profile, task pack, runner, and grader digests;
- evaluator relationships and conflicts;
- environment and actor manifests;
- trial outcomes and failure source;
- sanitized command records and content-addressed artifacts;
- measure values and evidence references;
- critical events and gate decisions;
- score reconstruction data;
- limitations, redactions, and integrity checks.

Large transcripts and streams may remain separate files. Every referenced file
has a role, media type, byte length, and SHA-256 digest.

JSON Schema validates document shape. A semantic validator must also verify:

- artifact IDs are unique and references resolve;
- recorded digests match artifact bytes;
- construct IDs match the selected track;
- task, measure, and dimension weights sum correctly;
- raw scores, gates, bands, and intervals can be recomputed;
- redacted artifacts have matching redaction records.

Secrets and personal data must be removed before publication. Redaction scope,
reason, and effect on reproducibility are mandatory evidence.

Evidence maturity is one of:

- `experimental`;
- `repeatable`;
- `independently_reproduced`;
- `validated`.

Only a different organization with no subject-maintainer role can mark a rerun
as independently reproduced. A Lathe maintainer's Lathe result cannot receive
that label.

## Validation program

The validation program is preregistered before pilot subject results are used
to change weights, gates, or boundaries.

### Pilot corpus

- Three controlled CLI variants share one backend and task set: deliberately
  degraded, neutral, and deliberately improved.
- At least six real CLIs cover local, remote, read-only, and mutating workflows.
- Comparisons occur only within matched capability groups.
- Lathe is at most one subject and receives no private task or grader access.
- Calibration and held-out task variants are separated before scoring changes.
- Human Core uses at least 24 participants.
- Agent Core uses at least three model families and ten repetitions per
  model-task condition.

### Experiments

#### V1 — Content coverage

Independent CLI, human-factors, and agent-evaluation reviewers map every
measure to a construct and maintain a public dispute log. The target is no
material omitted construct supported by a majority of reviewers.

#### V2 — Known groups

Reviewers blindly score degraded, neutral, and improved variants. The intended
ordering must hold in both tracks, and the 95% interval for
improved-minus-degraded must exclude zero.

#### V3 — Rater agreement

At least 20% of judgment-bearing trials are double-rated. The targets are
weighted kappa of at least 0.70 for categories and ICC of at least 0.75 for
continuous ratings.

#### V4 — Repeatability

Agent trials repeat the unchanged artifact and profile. Human repeatability is
tested only after stable familiarization or with matched cohorts; first-use
learning is not mislabeled as measurement noise. The targets are score ICC of
at least 0.75 and band agreement of at least 80%.

#### V5 — Construct behavior

Dimensions are compared with completion, errors, time, confidence, invalid
calls, and recovery. Preregistered directions must hold, and no dimension may
be explained mainly by one shallow proxy.

#### V6 — Held-out prediction

The rubric is frozen before held-out task variants are scored. Higher scores
must predict higher success or lower cost without worse correctness.

#### V7 — Robustness

The analysis uses leave-one-task-out runs, another platform, a second agent
harness, and dimension-weight changes of plus or minus 20%. At least 90% of
results must keep their band after already-borderline results are excluded.

#### V8 — Boundary calibration

Outcome curves and adjacent-band results test 60, 80, and 90. A boundary stays
only when it separates materially different outcomes.

#### V9 — Independent reproduction

An external evaluator recomputes a bundle and reruns selected subjects. Score
reconstruction must be exact. A rerun must be within five points, have
overlapping intervals, and retain the same gate state.

The reliability thresholds are v0 go/no-go targets, not universal scientific
constants.

### Failure policy

Rubric v0 does not pass validation by averaging experiments.

- Failure of V2, V3, V4, V6, or V9 blocks rubric v1.
- Failure of V7 narrows the supported claim or changes the profile.
- Failure of V8 changes the bands before v1.
- Every changed construct, weight, gate, or boundary is rerun on held-out data.
- Pilot scores remain experimental even when one experiment passes.

[NIST AI 800-2](https://doi.org/10.6028/NIST.AI.800-2.ipd) is an
initial public draft, not a final standard, but its separation of evaluation
objectives, implementation, analysis, and reporting informs this program.
[ACM Artifact Review and
Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current)
informs the distinction between available evidence and independently reproduced
results.

## Deferred until pilot evidence

Rubric v0 intentionally does not decide:

- a global leaderboard;
- a combined Human and Agent score;
- cross-category rankings;
- production-security certification;
- a universal task pack;
- implementation language or packaging;
- official badges;
- v1 weights or boundaries.

Human Core v0 also does not support a broad accessibility claim. Such a claim
requires an appropriate cohort, assistive-technology setup, and profile.

The next artifact is a small controlled task pack. The runner comes after the
profile and evidence contracts survive external review.

## References

- [ISO 9241-11:2018 — Usability](https://www.iso.org/standard/63500.html)
- [ISO/IEC 25022:2016 — Measurement of quality in
  use](https://www.iso.org/standard/35746.html)
- [The Open Group — Utility
  Conventions](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [NIST AI 800-2 — Automated Benchmark
  Evaluations](https://doi.org/10.6028/NIST.AI.800-2.ipd)
- [NIST AI 800-3 — Statistical Models for AI
  Evaluation](https://doi.org/10.6028/NIST.AI.800-3)
- [ACM Artifact Review and
  Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current)
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)
