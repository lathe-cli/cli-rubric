# CLI Rubric Vision

> Open, reproducible CLI experience evaluation for humans and AI agents.

[中文](VISION.zh-CN.md)

## Status

This is the founding vision of CLI Rubric.

It defines the project's purpose, values, boundaries, and standard of evidence.
It is not yet a scoring specification. No official score, badge,
certification, ranking, or claim of conformance exists until the project
publishes and validates a versioned rubric.

The scoring method must earn credibility through public review, empirical
validation, and independent reproduction. This document cannot grant that
credibility by declaration.

## Why CLI Rubric exists

Command-line interfaces are now used by two materially different populations:

1. humans who learn, explore, reason, recover from mistakes, and form
   preferences; and
2. AI agents that discover capabilities, construct invocations, interpret
   outputs, recover from failures, and act under explicit budgets and safety
   constraints.

A CLI can technically expose every required operation and still be difficult,
ambiguous, unsafe, or unpleasant to use. "Can use it," "works well," and
"prefers to use it" are different levels of quality.

Most existing CLI guidance is qualitative. Most automated checks measure
conformance, not experience. Most agent benchmarks measure the capability of an
agent or model, not the quality of the CLI interface through which it acts.
Simple checklists, one-shot demos, and opaque LLM judgments cannot close that
gap.

CLI Rubric exists to turn CLI experience into an open measurement discipline:

- clear constructs;
- public methods;
- real tasks;
- replayable evidence;
- separate Human and Agent results;
- explicit uncertainty and limitations; and
- a governance process in which every rule can be questioned.

## Vision

We want every CLI maintainer to be able to answer two separate questions with
evidence:

> **Human:** How well can people use this CLI, and do they want to use it
> again?
>
> **Agent:** How reliably and efficiently can AI agents use this CLI without
> guessing?

We want every reported score to be traceable from the displayed number back to
the rubric version, evaluation profile, task, invocation, observation, and raw
evidence that produced it.

We want CLI authors to optimize against the published standard. If that work
makes real human and agent outcomes better, the benchmark has created value.

## The first value: procedural fairness

CLI Rubric does not promise perfect or context-free objectivity. No experience
measure can honestly make that promise.

It promises procedural fairness:

- the rules are public;
- the same rules apply to comparable subjects;
- observations are separated from judgments;
- subjective measures are labeled as subjective;
- conflicts of interest are disclosed;
- uncertainty is reported rather than hidden;
- exceptions are explicit and reviewable;
- scoring changes are versioned;
- historical evidence remains available; and
- anyone can reproduce, challenge, or fork the method.

Fairness is not a project slogan. It is a property that must be visible in the
method and artifacts.

## What “CLI experience” means

CLI experience is an outcome of use in a declared context. It is not a property
that can be inferred from source code, help text, or a feature checklist alone.

Every meaningful evaluation therefore declares:

- the CLI and exact artifact being evaluated;
- the tasks and goals;
- the intended users or agents;
- their prior knowledge and available documentation;
- the operating system, shell, terminal, locale, and execution environment;
- the network, credentials, fixtures, and external services;
- the allowed time, tokens, tool calls, and other resources;
- the consequences and risk level of the operations; and
- the rubric and evaluation protocol version.

A score without this context is not an official CLI Rubric score.

## Two scores, never one total

CLI Rubric has two independent top-level tracks:

```text
CLI Rubric
├── Human Score
└── Agent Score
```

There is no combined Human + Agent score.

The tracks may share evidence collection, task fixtures, and low-level
conformance checks. They do not share a top-level weight, and one track cannot
compensate for failure in the other.

A project may publish:

- a Human Score only;
- an Agent Score only; or
- both scores side by side.

Missing evidence is reported as “not evaluated,” never guessed, silently
imputed, or converted to zero.

### Human Score

The Human Score measures outcomes for specified people completing specified
goals in a specified context.

Its construct is informed by established usability and quality-in-use work:
effectiveness, efficiency, satisfaction, interaction quality, and context of
use. The final public rubric must be self-contained and openly licensed; paid
standards may inform it but cannot become hidden normative dependencies.

Candidate dimensions include:

- onboarding and discoverability;
- task completion and result correctness;
- time, effort, and unnecessary interaction;
- command, option, and concept comprehensibility;
- feedback, progress visibility, and output readability;
- error prevention, diagnosis, and recovery;
- consistency and transfer of learning;
- safety, reversibility, and user control;
- accessibility within the declared terminal context; and
- satisfaction, confidence, and preference for repeated use.

The Human Score must not be derived from static linting alone. A validated
evaluation combines appropriate evidence such as:

- deterministic behavioral checks;
- representative task completion;
- observed errors and recovery paths;
- time and interaction measurements;
- controlled comparisons;
- participant feedback; and
- validated questionnaires where they are appropriate.

Questionnaires such as SUS or workload instruments such as NASA-TLX may provide
supporting evidence. They are not, by themselves, a complete measure of CLI
quality or delight.

Every Human Score discloses the participant profile, sample, recruitment
method, task order, study design, exclusions, and uncertainty. When comparing
CLIs or versions, the protocol should use randomization or counterbalancing
where appropriate to reduce learning and order effects.

### Agent Score

The Agent Score measures how reliably and efficiently specified AI agent
systems achieve specified goals through the CLI under a declared execution
profile.

It does not measure whether an agent has feelings or literally “likes” a tool.
At the highest band, “preferred” means the interface produces consistently
better task outcomes, lower interaction friction, or a validated revealed
preference under controlled comparison.

Candidate dimensions include:

- capability and command discovery;
- correct mapping from intent to invocation;
- schema, parameter, and authentication clarity;
- machine-readable output and stable error semantics;
- semantic correctness of completed tasks;
- detection and repair of invalid actions;
- determinism and resistance to environmental ambiguity;
- interaction efficiency, including tool calls, tokens, retries, and time;
- context economy and output relevance;
- safe preview, confirmation, idempotency, and reversibility where applicable;
- behavior in non-interactive environments; and
- recovery from partial failures, stale state, and constrained resources.

The Agent Score must isolate interface quality from model capability as far as
the protocol allows. Official evaluation profiles therefore require:

- fixed tasks, budgets, prompts, and harness behavior within a comparison;
- multiple repeated trials for stochastic systems;
- exact model, provider, version, agent, and harness disclosure;
- a representative panel rather than a single favored model when making broad
  claims;
- matched or paired comparisons where useful;
- decomposition of backend failure, agent failure, and interface failure; and
- explicit limits on what may be generalized beyond the tested task set.

Deterministic graders are preferred whenever correctness can be checked
directly. An LLM judge may be used only for constructs that cannot be scored
reliably by deterministic means. Its prompt, model, raw judgments, calibration
set, agreement with qualified human labels, failure modes, and uncertainty must
be published. An unvalidated LLM opinion is not ground truth.

## Score bands

Each track uses its own 0–100 score. The same numerical bands communicate a
shared product ambition, while the Human and Agent constructs remain separate.

- **0–59 — Unusable.** People or agents cannot reliably achieve the declared
  goals.
- **60–69 — Usable.** People can complete core goals with material friction;
  agents can complete them with material friction or supervision.
- **70–89 — Good.** Human use is effective, understandable, and efficient;
  agent use is reliable, discoverable, and efficient.
- **90–100 — Loved or preferred.** People show strong confidence,
  satisfaction, and preference; agents show consistently low friction and
  superior controlled outcomes.

The intervals are unambiguous: 60, 70, and 90 start the next band.

These thresholds are the project's initial semantic contract, not scientific
constants and not values supplied by ISO or any other external authority.
Before rubric v1, the project must test whether they correspond to meaningful
differences in observed outcomes. A material change to their meaning requires a
new scoring version.

A displayed score must include:

- its track;
- score and band;
- rubric version;
- evaluation profile;
- evidence maturity;
- uncertainty or observed dispersion where applicable; and
- material limitations.

If uncertainty spans a band boundary, the report must show that ambiguity
instead of presenting a stronger conclusion than the evidence supports.
Meaningless decimal precision is prohibited.

## Scores are projections, not the evidence

A 0–100 number is useful for communication, regression detection, and setting a
quality ambition. It is also lossy.

Every top-level score must remain decomposable into:

- dimension scores;
- individual measures;
- applicable gates and caps;
- raw observations;
- scoring transformations;
- weights;
- uncertainty; and
- excluded or unavailable evidence.

Weights and aggregation rules must be public and versioned. Sensitivity
analysis should show when a result depends heavily on a contested weight.

Some failures cannot be averaged away. A CLI that corrupts data, reports
success on failure, exposes secrets, or cannot complete a critical declared
task must not earn a high score by accumulating unrelated polish points.
Versioned rubrics may define public critical gates or score caps. The evidence
that triggered them must be visible.

## Evaluation profiles and comparability

There is no honest universal CLI score independent of context.

Official reports use versioned evaluation profiles that may declare:

- CLI category and capability class;
- local, remote, or hybrid operation;
- read-only, mutating, or destructive risk;
- novice, occasional, or expert human cohorts;
- agent panel and autonomy level;
- supported operating systems and shells;
- interactive or non-interactive execution;
- documentation and network availability;
- task pack and data fixtures; and
- resource budgets.

Scores are directly comparable only when the rubric, profile, task pack,
environmental assumptions, and material protocol are compatible. Reports must
not rank incompatible CLIs as if they measured the same thing.

Cross-platform claims require cross-platform evidence. A result obtained only
on one operating system is scoped to that system.

CLI Rubric may eventually support comparative views, but it will not begin with
a global leaderboard. Measurement validity comes before competition.

## Evidence bundle

Every official evaluation produces a portable evidence bundle. At minimum it
records:

### Subject

- CLI name, version, source, and artifact digest;
- installation method and dependency lock information;
- declared supported platforms and capabilities;
- configuration and enabled feature set; and
- evaluator relationship to the project.

### Method

- CLI Rubric tool and commit or release;
- rubric, profile, task pack, and grader versions;
- scoring rules, weights, gates, and transformations;
- environment image or complete environment manifest;
- fixtures, generation seeds, and setup procedures; and
- deviations from the canonical protocol.

### Execution

- command invocations and working context;
- sanitized stdin, stdout, and stderr;
- exit status, timing, signals, retries, and resource use;
- task state before and after execution;
- grader inputs and outputs; and
- enough ordering information to replay the evaluation.

### Human evidence

- participant and cohort definition;
- study instructions and task order;
- observations and derived measures;
- questionnaire instruments and responses in an ethical, privacy-preserving
  form;
- exclusions and missing data; and
- consent, privacy, and retention statements where human research is involved.

### Agent evidence

- model and provider identifiers available at evaluation time;
- agent and harness versions;
- system and task prompts;
- tool exposure and permissions;
- model parameters, budgets, and stopping conditions;
- complete sanitized tool-call trajectories; and
- per-trial outcomes and failure classifications.

### Result

- component and top-level scores;
- uncertainty, dispersion, and trial counts;
- critical findings, caps, and limitations;
- a machine-readable scoring trace; and
- integrity hashes for the evidence.

Secrets, personal data, and unsafe payloads must be redacted or represented by
safe references. Redaction rules and their effect on reproducibility must be
declared. CLI Rubric must not require covert telemetry.

## Evidence maturity

Not every report deserves the same confidence.

Reports must identify whether their results are:

- experimental;
- repeatable by the original evaluator;
- reproduced by an independent evaluator; or
- validated across materially different environments or cohorts.

The exact maturity model will be specified publicly. Until a result has
independent reproduction, it must not be presented as independently verified.

## How the method earns credibility

CLI Rubric will not borrow credibility merely by citing established standards
or publishing source code. It must validate that its own measurements work.

The methodology program must address:

### Content validity

Do the rubric dimensions cover the important parts of human and agent CLI
experience? Evidence includes open expert review, maintainer and user feedback,
failure analysis, and documented coverage gaps.

### Construct validity

Do the measures actually reflect the concepts they claim to measure, rather
than superficial proxies such as flag count or help-text length?

### Criterion validity

Do higher scores predict better task success, lower effort, better recovery,
and stronger preference in external observations?

### Reliability

Do repeated runs, different task samples, different qualified raters, and
independent implementations produce sufficiently consistent conclusions?

### Robustness

Does the conclusion survive reasonable changes in models, cohorts,
environments, task selection, and scoring weights?

### Uncertainty

What part of the variation comes from the CLI, task difficulty, humans, models,
harnesses, graders, and random sampling? Reports must distinguish performance
on the fixed benchmark from claims about a broader population of possible
tasks.

### External reproduction

Can a party that did not design the CLI or rubric reproduce the evidence and
reach a compatible conclusion?

The rubric remains experimental until this validation work supports the claims
attached to its scores.

## Fair treatment of optimization and gaming

CLI authors are explicitly allowed and encouraged to improve against the
published rubric.

Adding structured output, correcting exit codes, improving help, making errors
actionable, reducing unnecessary prompts, adding safe preview, or improving
task success is not benchmark gaming. It is the intended social value of the
project.

The method must distinguish this from test-specific behavior that raises a
score without improving the underlying experience. It should use:

- diverse representative tasks;
- negative and recovery cases;
- generative or parameterized fixtures where appropriate;
- held-out validation performed under a publicly declared procedure when
  needed;
- cross-version and cross-environment checks;
- sensitivity analysis; and
- evidence that improvements transfer to outcomes outside a single item.

There will be no secret quality criteria or hidden weights. If any task instance
is temporarily withheld to preserve measurement integrity, the policy,
generation method, access rules, release schedule, and conflict controls must
be public and must not prevent independent reproduction of released results.

## Independence and the Lathe conflict

CLI Rubric is initiated inside the `lathe-cli` organization by people connected
to Lathe. This creates an obvious potential conflict of interest. The project
will disclose it rather than pretend that a name removes it.

The following commitments are foundational:

- Lathe receives no private rubric, fixture, weight, prompt, or exception.
- Lathe is evaluated from public artifacts under the same released protocol as
  comparable CLIs.
- Lathe-specific capabilities earn credit only when the public rubric defines
  a general outcome that any CLI can satisfy.
- A poor Lathe result must be published as honestly as a strong result.
- Reports disclose evaluator, sponsor, and maintainer relationships.
- Maintainers recuse from adjudicating material disputes where they have a
  direct conflict once sufficient independent governance exists.
- Until independent reviewers and reproductions exist, project-produced Lathe
  reports are labeled maintainer-produced, not independent.

No vendor, including Lathe, may buy a score, suppress a valid result, or receive
advance access unavailable under the public protocol.

## Open governance

The scoring standard belongs to its community of users, evaluated projects,
evaluators, and researchers.

The governance model must provide:

- public proposals for material rubric changes;
- rationale and evidence for every criterion, weight, gate, and threshold;
- public review periods for scoring changes;
- semantic versioning of rubrics, profiles, schemas, and task packs;
- immutable identification of the method used for historical results;
- a correction and appeal process;
- disclosed conflicts and recusal rules;
- documented release and deprecation policy;
- a path for independent implementations and alternative weightings; and
- a process for recognizing independent reproduction.

Corrections must preserve an audit trail. Historical scores may be recomputed
under a new rubric, but they must not be silently rewritten as if the new
method had always applied.

The evidence schema should permit others to compute alternative scorecards.
Only results following the official versioned protocol may use the official
CLI Rubric designation for that version.

## Delivery form remains open

The project has not selected an implementation language or final packaging
model.

It may become:

- a standalone CLI;
- a reusable library;
- a CI integration;
- a GitHub Action;
- an agent or editor plugin;
- a hosted report viewer;
- a collection of open task packs; or
- a combination of these.

This decision follows the measurement design. The project will not lock a weak
method behind a polished tool.

The durable product is the open protocol and evidence model. Software is the
reference implementation of that protocol.

## Initial scope and non-goals

The first validated release should focus on non-full-screen command-line
programs that can be exercised safely in isolated fixtures.

Initial non-goals:

- evaluating the overall quality of the underlying service or API;
- certifying security, legal compliance, or production readiness;
- rating graphical interfaces, IDE extensions, or full-screen TUIs;
- declaring one CLI framework universally superior;
- measuring only startup performance or implementation code quality;
- producing a universal ranking across incompatible CLI categories;
- replacing human research with an LLM judge;
- treating a static best-practice checklist as complete experience evidence;
- hiding scoring logic to prevent optimization; and
- granting Lathe a privileged path.

Security, accessibility, performance, and reliability may contribute where they
affect the declared experience. A CLI Rubric score is not a substitute for a
specialized audit or certification in those domains.

## Roadmap to a credible v1

### Phase 0 — Founding constitution

- publish this vision;
- disclose the Lathe relationship;
- establish that Human and Agent scores remain separate;
- prohibit official scores before method validation; and
- invite criticism of the constructs and governance commitments.

### Phase 1 — Open measurement design

- define the Human and Agent constructs;
- publish the evidence schema and experiment manifest;
- define evaluation profiles and comparability rules;
- create deterministic reference fixtures and failure classifications;
- propose rubric dimensions, gates, weights, and uncertainty reporting;
- define privacy and safe-execution requirements; and
- publish a validation plan before seeing benchmark outcomes.

### Phase 2 — Pilot and calibration

- evaluate diverse CLIs, including Lathe and non-Lathe tools;
- include deliberately weak and deliberately improved reference interfaces;
- run controlled human studies for the Human track;
- run repeated multi-model, multi-agent trials for the Agent track;
- measure inter-rater and test-retest reliability;
- test sensitivity to task samples, weights, environments, and cohorts;
- examine whether scores predict external outcomes; and
- calibrate or revise the 60/70/90 band meanings from evidence.

All pilot scores remain experimental.

### Phase 3 — Rubric v1

- freeze a reviewed v1 protocol;
- release the reference runner and machine-readable schemas;
- publish versioned task packs and graders;
- publish complete evidence bundles for reference evaluations;
- document limitations and unresolved validity threats; and
- support independent reproduction before claiming broad authority.

### Phase 4 — Ecosystem trust

- recognize compatible independent implementations;
- support third-party task packs without weakening comparability;
- establish durable multi-stakeholder governance;
- maintain longitudinal score histories without silent reinterpretation;
- add comparative views only where statistical and contextual validity permit;
  and
- evolve the standard through public evidence.

## What success looks like

CLI Rubric succeeds when:

- a maintainer can reproduce every finding behind a score;
- a disputed criterion can be challenged with evidence and changed publicly;
- independent evaluators can reach compatible conclusions;
- higher scores predict better real task outcomes;
- a CLI improvement raises both the relevant component measure and external
  user or agent outcomes;
- users can distinguish experimental, repeatable, and independently reproduced
  results;
- Lathe is treated exactly like any comparable subject;
- projects proudly improve against the rubric because the improvements help
  their users; and
- the community trusts the process even when it disagrees with a result.

The deepest measure of success is not the number of CLIs scored. It is the
number of CLI experiences that become measurably better for people and agents.

## Reference foundations

These sources inform the research direction. They are not endorsements of CLI
Rubric, and CLI Rubric does not claim conformance merely by citing them.
Normative rubric releases must remain openly available and self-contained.

### Human experience and software quality

- [ISO 9241-11:2018 — Usability: Definitions and
  concepts](https://www.iso.org/standard/63500.html)
- [ISO 9241-110:2020 — Interaction
  principles](https://www.iso.org/standard/75258.html)
- [ISO 9241-210:2019 — Human-centred design for interactive
  systems](https://www.iso.org/standard/77520.html)
- [ISO/IEC 25010:2023 — Product quality
  model](https://www.iso.org/standard/78176.html)
- [ISO/IEC 25022:2016 — Measurement of quality in
  use](https://www.iso.org/standard/35746.html)
- [The Open Group Base Specifications Issue 8 — Utility
  Conventions](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html)
- [Command Line Interface Guidelines](https://clig.dev/)
- [SUS: A “Quick and Dirty” Usability
  Scale](https://doi.org/10.1201/9781498710411-35)
- [NASA Task Load Index](https://humansystems.arc.nasa.gov/groups/tlx/)

### Evaluation, evidence, and agents

- [ACM Artifact Review and
  Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current)
- [NIST AI 800-2 — Practices for Automated Benchmark Evaluations of
  Language Models, initial public draft](https://doi.org/10.6028/NIST.AI.800-2.ipd)
- [NIST AI 800-3 — Expanding the AI Evaluation Toolbox with Statistical
  Models](https://doi.org/10.6028/NIST.AI.800-3)
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)
- [Berkeley Function Calling
  Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard)
- [τ-bench](https://github.com/sierra-research/tau2-bench)

## Final commitment

CLI Rubric will publish evidence before authority, method before leaderboard,
and limitations beside every score.

Human experience and agent experience will remain separate.

The rules will be open. The implementation will be inspectable. Criticism will
be part of the system. Improvement against the standard will be welcomed.

Credibility will be earned one reproducible result at a time.
