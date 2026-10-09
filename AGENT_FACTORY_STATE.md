# MPT Agent Factory — Project State

> Source of truth for agents working on this repository.
> Update this file after meaningful architecture, runtime, benchmark or branch changes.
> Do not store secrets, API keys or credentials here.

## Independent spatial audit — 2026-10-09

From published `0e4a0aa`, fixed CPU cohort on6 retained originals completes: SIFT full/nativeROI±8 and HSV three-threshold masks, no VLM/GPU/generation/downloads/services. C/recolor align locally; A and B both lack finite nativeROI fit, so absence of matches cannot judge shape. Color masks select incomplete parts/background; Dice ordering reverses with thresholds. All scores remain diagnostic/uncertain, no admission. Added isolated reproducible script/tests only, no app/routing/gates/deps/workflow changes. API FailedEstimation correction preserved with real RED→GREEN and unchanged parameters.89 fresh tests pass exit0,1expected warning. [Report](docs/SPATIAL_GEOMETRY_AUDIT_REPORT.md). Next explicit complete-object masks/part landmarks and independent review before calibration; no further prompt fishing. Stable tracked intact; preserve ignored SVG/originals. Closing SHA via history/origin.

## Current visual judge selection — 2026-10-08

Latest continuation from `3e2b873`: single-component controls complete, 20 retained VLM requests /0generations /0timeouts/truncations/retries. Both models recognize visible handle holes and target absence; contact splitting remains inconsistent (Qwen3.5 red2/blue1, Qwen3-VL aggregated1/1). Both report one shaft-band region for all4keys; B still no hint despite human-reviewed shape change. 96 fresh focused tests pass, code unchanged (520+17 previous suite remains historical). Six own8092 closed, stable intact. Profiles/raw/replays/20localSVGs preserved. [Report](docs/ISOLATED_COMPONENTS_REPORT.md). Next independent spatial/shape verification audit; no admission or prompt-fishing rescue.

Latest continuation from `fe63c61`: normalized location boxes/IoU review protocol added; 5 retained requests across existing Qwen3.5/Qwen3-VL candidates, 0 generations. Qwen3.5 red complete but shifted boxes, blue truncated/unavailable, absence unattempted. Qwen3-VL three complete but misses visible handle holes and merges contacts. No identity/admission; offline SVGs/replays preserve errors. 520 tests +17 subtests pass, 1 skipped, exit0. Both owned8092 closed, stable intact. [Report](docs/VISUAL_LOCATION_DIAGNOSTICS_REPORT.md). Next: component-by-component requests with independent region review; neither judge factual-ready. Prior results below remain historical and separate.

Latest continuation from `7c1871c`: 11 retained-image VLM requests, 0 generations. Same-prompt decoding contrast and explicit-format controls distinguish malformed JSON from weak component semantics; four key inventories still miss human-reviewed major change B and aggregate multiple bands. All comparisons uncertain, no admission. Added explicit offline diagnostic store injection to the experimental MPT caller; default None, no automatic wiring/inference/routing/flags. 495 tests +17 subtests pass, 1 integration skipped, exit 0. All five owned 8092 servers closed; stable protected. [Report and next step](docs/COMPONENT_DECODING_DIAGNOSTICS_REPORT.md). Next: coordinate-based location evidence with offline review; current judge is not factual-ready. Historical sections below remain distinct.

Latest on631afff: explicit target/component profile prototyped.4requests: V1 contradictory rejected,V2 identifies present/absent target but marks visiblepartsabsent,plain description recognizes mouth/two contacts.109tests pass; finalcoverage flags zero observed components,neveridentity/admission. [Report](docs/TARGET_COMPONENT_OBSERVATIONS_REPORT.md). Allown8092closed,stable intact,0generation/app/routing changes. Next controlledsame-prompt schema/free-output contrast; component semantics not ready.

Latest onb51e2b3: generic observer --plan tested on5 retained mug images;5requests complete,92 tests pass. No category/count differences from color/vapor, all comparisonsuncertain/no decisions. Coverage omits handle opening/distinct contacts, no reviewed structuralnegative, so not factual-ready. [Mug report](docs/MUG_GEOMETRY_OBSERVATION_REPORT.md). Own8092 closed,stable intact,0generation/app/routing changes. Next: explicit target presence/component coverage using an existing absence control.

Latest on61c1285: offline geometry-review-priorities-1 implemented,87 tests pass. Model structure/count/incomplete signals and human local/structural changes stay distinct; no admission/rejection/identity inference. A/B/C replay preserves both hints and human annotations.0 new inference/GPU/generations,experimental script/tests only, no app/routing changes. [Priority report](docs/GEOMETRY_REVIEW_PRIORITIES_REPORT.md). Next: additional perceptual controls from another family before opt-in diagnostic integration.

Human review received on3d60ade: A shape preserved/minor ring enlargement; B completely altered; C no visible change. Separate annotation retained without rewriting historical labels. Model hints miss A size nuance, align with B gross change and falsely flag C counts; comparator staysuncertain/no admission. [Current observation report](docs/VISUAL_GEOMETRY_OBSERVATIONS_REPORT.md). No pending question for these pairs, no new GPU/tests/app changes. Next: conservative hint policy with explicit severity/uncertainty and additional controls; no production tolerance or approval inferred.

Latest onab4b032:4 independent single-image geometry inventories complete,69 offline tests pass. Experimental comparator emits review hints and alwaysuncertain/no admission; observes key opening difference but false count differences remain. User closed8080 to free RAM;own8092 closed,stable intact. [Observation report](docs/VISUAL_GEOMETRY_OBSERVATIONS_REPORT.md). Human A/B/C review requested and pending; do not infer answers or integrate routing. No new generation/dependency/workflow/app changes.

Latest QA audit on0624618: full blind16-case contract TP5/TN9/FP0/FN1,0timeouts,mean9.125s; MPT3-hands now detected but deformed key missed.3 separate component probes detect key while rejecting2 positives (one geometry error,one inconsistent text verdict).19 new VLM requests,0 generations/source/routing changes,own8092 closed,stable intact. [Full QA report](docs/VISUAL_JUDGE_FULL_QA_REPORT.md). Not ready for automatic factual admission; next independent geometry review and structured evidence design. All previous protocol metrics remain separate.

Prefill continuation complete on9f42964: after user closed8080 and game,6 fresh-server controls succeed. Focused blind counts detect3 hands in negative full/crop; positive full/full+crop correctly2, crop alone falsely3. Earlier text timeout under gameplay preserved as resource-confounded;7 new requests/0 generations, owned8092 closed. No automatic QA admission or source changes. [Diagnosis](docs/VISUAL_JUDGE_PREFILL_DIAGNOSIS.md). Next: blind counts in full QA and deformed-key/reference controls; keep OCR/fail-closed. Preparation and historical comparisons below remain separate.

Next diagnosis prepared from9bfec74: six fresh-server controls (text/full/crop/full+crop; blind watch-hand counts), no new GPU requests.58 offline tests pass.8080 reopened by user; globalVRAM6731/12288MiB and freeRAM7.22GiB. Pending temporary user closure of8080 before owned8092 tests; no shared service stopped. See newest section of [candidate handoff](docs/VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Historical comparison below remains unchanged.

Comparison completed after user closed8080. Experimental next candidate:Qwen3.5-9B Q4_K_M/F16. Base16-case matrix:4/6 defects detected,9/9 positives accepted,2FN, no unavailable; mean27.786s, peakglobal10448MiB. Qwen3-VL8B detects0/6 and has3timeouts. No automatic admission/routing:deformed factual key/three-hand MPT watch remain missed. ROI/blind-count diagnostics timed out; isolate prefill before integration.55 focused tests pass.42 VLM requests,0 generated images, no production/default/dependency/workflow changes. Own8092 closed; user can reopen8080.

Read [comparison report](docs/VISUAL_JUDGE_COMPARISON_REPORT.md) and [current candidate handoff](docs/VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Stable protected HEAD remains6d27ba4963ffe469d635db71eaeec506a8ff4b61. Preparation block below is historical.

## Visual judge candidates — 2026-10-08, preparation pending GPU clearance

User authorized Qwen3.5-9B/Qwen3-VL-8B downloads and a bounded retained-image comparison. Four pinned GGUFs (12.79GB) and portable official CUDA12.4 llama.cpp b11497 verified;51 offline tests pass. Zero comparative GPU inference so far: shared8080 server remains resident, GPU~7.7GB used after Comfy cached weights unloaded, RAM~6.1GiB free. Await user closing8080 or explicitly choosing partial offload; never infer consent to stop shared services. Read [candidate handoff](docs/VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Production/defaults/stable unchanged; no candidate selected.

## Current experimental QA — 2026-10-08

Base87c7ba5, audit1ec050a, implementationd8de6a5. Scoped offline visual QA and local no-thinking judge policy remain opt-in, without persisted flags or automatic routing. 387 tests and17 subtests pass,1 integration skipped. Retained16-image dataset: only3 decisions,13 uncertain; mean4.5073s/median4.2692s. Speed improved, perceptual reliability remains incomplete; factual/continuity identity is fail-closed. Zero new generations, models, dependencies, workflows, jobs or restarts. Stable HEAD remains6d27ba4963ffe469d635db71eaeec506a8ff4b61.

Read [visual QA report](docs/VISUAL_QA_REPORT.md) and [current handoff](docs/VISUAL_QA_HANDOFF.md). Next requires stronger visual evidence and independent labels on existing artifacts; do not enable routing or assume the text-only8080 judge can see images.

## Current experimental candidate — 2026-10-08: Klein 4B integration

Branch `factory/image-model-routing-modernization`, base `1c7de1a`. Explicit opt-in MPT caller, separate T2I/Edit aliases and quality/conditioning metadata; conservative technical fallback, no semantic fallback. Experimental scene admission requires available, explicit QA pass. Stable remains `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.

Windows validation: 241 tests and 2 subtests pass, 42 new caller/pipeline cases. Ten Klein GPU requests and two small comparisons succeeded technically; factual geometry/cardinality and caption-QA uncertainty prevent promotion. Two-reference target resolution exercised; three references and full video deferred. See [current report](docs/FLUX_KLEIN_4B_AUTONOMOUS_REPORT.md) and [handoff](docs/IMAGE_MODEL_ROUTING_HANDOFF.md). No Factory, stable, dependencies, workflows or persisted config changes. Next: validate visual evidence/QA efficiency on retained artifacts before more generation or automatic routing.

## Current candidate — 2026-10-01: evidence, continuity and corrective retry

Isolated branch: `factory/evidence-continuity-fix`, based on published narration
candidate `188001bf82fee2518002c9105dec77c4a49cb573`. Stable remains unchanged at
`6d27ba4963ffe469d635db71eaeec506a8ff4b61`. See
`docs/EVIDENCE_CONTINUITY_HANDOFF.md` for recovery details, tests and manual checks.

The user validated the second controlled Windows SX-70 run
`15825038-3597-4b77-85ee-0b9f0a9a5c27`: internal narration.srt, 23 subtitle blocks,
9 semantic scenes, 7 Precision / 2 Standard, active references and continuity,
completed diagnostics and technically valid MP4. These are user-reported results,
not a generation performed in this session. Statements below that this corrected
benchmark remains pending are historical.

The candidate discards rejected visual alternatives at the coverage gate, scopes
continuity to the intended target, and retains the original when the single cheap
duplicate correction does not improve similarity. When an earlier scene already
established covered primary identity, the fallback can reuse that identity for an
exterior reference shot; no unsupported mechanism or action is reused. Otherwise a
conservative generic context remains. Diagnostics record both metrics and selection.
Narration timing, references/anchors, Balanced defaults and its soft planning budget
remain intact. No Factory changes, new dependency declarations, heavy evaluators or
live generation. The former worktree was absent from the restored environment; its
recorded patch was recovered onto the same published base, not redesigned.

## Candidate update — 2026-09-30: narration timing independent of rendering

Branch/worktree: `factory/narration-timeline`, based on stable
`6d27ba4963ffe469d635db71eaeec506a8ff4b61`. Stable is not modified or merged.

The first Factory SX-70 run (`c3ac5e07-4ad2-4a65-bdfa-97cbba9994a8`) completed
technically but did not exercise Precision: 11 Standard scenes, refs=0. It had
subtitle_enabled=false and no controlled video_script. The missing subtitle
timeline bypassed structured planning and the Balanced scene budget. The user
also confirmed that the supervisor was not running during the collection delay;
do not infer another PID/ComfyUI/SQLite cause from that delay.

This candidate adds prepare_narration_timeline: reuse existing subtitle timing
or serialize sub_maker into a sentence-level internal narration.srt. It never
changes subtitle_enabled, passes that internal path to the renderer, invokes
Whisper or requests another TTS. The visible subtitle path remains empty when
disabled. Missing alignment/custom audio retains a uniform fallback capped at
the profile scene budget. Balanced remains 9 scenes, ratio 0.65, one candidate,
direct accept, existing steps and reference rules; no heavy evaluator is added.

Factory separately fixes examples/polaroid-job.json to carry the user's exact
seven-paragraph controlled script. That input must accompany this candidate
before repeating SX-70; a generated narration is not the same benchmark.

Offline validation in Linux Work (Python 3.12.14):

```text
MPT_RUN_INTEGRATION_TESTS=0 /workspace/scratch/845a021772d1/MPT-Agent-Factory/.venv/bin/python -m pytest -q test/services/test_narration_timeline.py test/services/test_task.py test/services/test_qwen_quality_v31.py test/services/test_voice.py test/services/test_subtitle.py
173 passed, 6 skipped, 1 warning, 20 subtests passed in 5.14s

/workspace/scratch/845a021772d1/MPT-Agent-Factory/.venv/bin/python -m compileall -q app test/services/test_narration_timeline.py
exit 0
git diff --check
exit 0
```

This is the five-file affected-area suite, not a new full-core baseline. Eleven
new cases cover hidden/visible subtitles, render arguments, nine-scene timing,
structured Precision output propagation (mock LLM), fixed-script passthrough,
no Whisper, missing/invalid alignment, existing timing, real Edge SubMaker and
legacy offsets. No live providers, Qwen, ComfyUI or real video generation ran.
The warning is pydub's existing Python audioop deprecation. Initial new-test
fixtures had two missing video_subject errors, corrected before this result.
The expanded suite initially lacked pydub, then google-genai; the already-declared
versions 0.25.1 and 2.11.0 were installed only in the test environment. No dependency
files changed. Native Windows validation and the corrected live benchmark remain
pending. The historical reported 126/2/20 baseline below is not overwritten.

## 1. Objective

Turn the current MoneyPrinterTurbo customization into an autonomous development + video-production system that can:

1. generate videos from queued benchmark or production jobs;
2. inspect generated images/video and diagnostics;
3. detect systematic failures such as identity drift, continuity breaks or unsupported factual visuals;
4. create isolated code experiments;
5. run tests and benchmark candidate changes;
6. keep only changes that improve quality without regressions;
7. later add a publishing agent for approved TikTok / YouTube Shorts outputs.

Core philosophy:

```text
plan well -> generate once -> check the minimum necessary
```

Avoid:

```text
generate many candidates -> score everything heavily -> attempt to rescue
```

Do not add topic-specific keyword hacks. Changes should generalize across subjects.

## 2. Current Repository

Repository:

```text
JaviLopez2/CustomVideoGenerator
```

Active development branch:

```text
moneyprinter_qwen21_quality_v3_1
```

Primary local path:

```text
D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\MoneyPrinterTurbo
```

Portable Python:

```text
D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe
```

Do not assume Windows Store `python.exe` is the intended interpreter.

Untracked `.bak` and backup directories intentionally exist locally. Do not use `git add .`.

## 3. Hardware

Current development machine:

```text
CPU: Intel Core i7-12700
RAM: 32 GB
GPU: NVIDIA RTX 3060 12 GB
OS: Windows
```

GPU-heavy services should normally run sequentially where possible. Avoid assuming enough VRAM exists to keep multiple large vision/image models loaded simultaneously.

## 4. Runtime Services

Expected local stack:

```text
8080 -> llama.cpp / local Qwen text model
8188 -> ComfyUI
8090 -> ComfyUI-to-OpenAI bridge
8501 -> MoneyPrinterTurbo Streamlit UI
```

Current local text model:

```text
HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive:IQ3_M
```

ComfyUI launch currently uses:

```text
--disable-async-offload --disable-pinned-memory
```

Qwen Image 2.1 is the Precision image generator.
Klein is fallback only.

## 5. Current Image-Generation Architecture

Balanced target:

- approximately 9 scenes;
- one Qwen Precision candidate;
- direct accept;
- max 3 references per Qwen scene;
- 20 Balanced steps;
- no heavy image selector in Balanced;
- only one corrective retry after a true technical failure or actionable near-duplicate;
- no Florence/BiRefNet in Balanced generation path.

Quality mode may retain heavier multi-candidate logic.

Qwen workflow:

```text
qwen-image-2.1-precision
```

Important: audited Qwen workflow runs CFG=1. Do not blindly raise CFG. Important exclusions belong in positive conditioning because the unconditional/negative branch is skipped at CFG=1.

## 6. Reference System

Manual references support roles such as:

```text
identity
detail
internal
context
continuity
```

Key rules:

- identity = whole primary referenced entity;
- a produced output is not automatically the primary subject;
- detail/internal/context evidence must be semantically supported by the user description;
- max 3 Qwen references;
- identity anchor should preserve the source entity, not contaminate a produced output;
- continuity anchor represents the same physical instance/content at a previous stage.

## 7. Current Planner / Safety Gates

Current planner has structured metadata including:

```text
canonical_subject
reference_need
reference_target
evidence_scope
reference_critical
includes_primary_subject
safe_visual_alternative
continuity_key
continuity_description
coverage_status
planner_validation
factual_audit_status
```

Evidence scopes:

```text
externally_visible
specialized_visible
hidden_internal
contextual
```

Reference targets:

```text
primary_subject
output
secondary_subject
environment
none
```

Unsupported hidden/specialized scenes should fall back to externally observable evidence instead of fabricating convincing internal mechanisms.

## 8. Current Version — V3.2.1

Latest implemented direction builds on V3.2.

V3.2 introduced:

- hard primary identity lock;
- semantic evidence checks;
- automatic temporal continuity groups;
- sequential continuity edit chain;
- continuity diagnostics;
- stronger reference descriptions in UI;
- diagnostics schema version 3.

V3.2.1 adds generalized fixes discovered during the Polaroid benchmark:

- produced outputs are separated from the primary source entity even if the source model name appears in the output description;
- externally-visible `detail` scenes still require matching detail evidence;
- continuity chains reset when the primary/source object leaves frame so the entire source frame is not recursively copied into the produced output;
- Qwen prompt explicitly blocks recursive picture-in-picture / nested copies of reference frames;
- identity references can be scoped only to a visible source entity in composite scenes;
- closing scenes can inherit the previous output continuity group when the final output and source entity appear together.

Relevant V3.2.1 commits created during the latest iteration include:

```text
8c87159  V3.2.1 planner: separate produced outputs, enforce semantic detail evidence
730c6ea  V3.2.1 continuity: isolate output stages and prevent identity recursion
6fadab1  V3.2.1 planner: keep derived outputs separate without false primary visibility
54c560b  V3.2.1 tests: output identity separation and continuity anti-recursion
```

## 9. Current Validation Status

Latest reported focused/full test run after pulling current changes:

```text
126 passed
2 skipped
20 subtests passed
~50.67 seconds
```

Do not treat future code as validated until its own compile/tests and benchmark run complete.

## 10. Current Benchmark

Primary benchmark topic:

```text
Cómo funciona una Polaroid SX-70: desde que pulsas el disparador hasta que aparece la fotografía.
```

Purpose of benchmark:

- preserve real product identity;
- avoid fabricated hidden/internal mechanics when references do not support them;
- keep the same produced instant photo across development stages;
- preserve both output continuity and source-camera identity when they appear together;
- avoid recursive image-in-image contamination.

Manual SX-70 reference pack currently uses:

```text
01_sx70_general_identity.png          identity anchor
02_sx70_primary_front.jpg             identity
03_sx70_alternate_threequarter.jpg    identity
04_sx70_profile_side.jpg              identity
05_sx70_rear_specialized.jpg          identity
06_sx70_detail_front_controls.jpg     detail
```

There is intentionally no internal reference.

The benchmark is a generalization test, not a reason to add SX-70-specific code.

## 11. Current Observed Failure Pattern Before V3.2.1

V3.2 proved that the continuity chain technically works, but exposed three structural issues:

1. continuity started from a frame containing both source camera + produced photo, causing the source camera to be copied inside the photo;
2. externally-visible `detail` could incorrectly be accepted through generic identity evidence;
3. a final composite scene could show the primary camera but still route Standard and drift to a different camera.

V3.2.1 is intended to address these three failures generically.

## 12. Next Immediate Product Goal

Build a separate project, tentatively:

```text
D:\Apps\MPT-Agent-Factory
```

Do not place the orchestration supervisor inside the core MPT codebase unless there is a strong architectural reason.

Initial autonomous architecture:

```text
Supervisor
  -> Video Agent
  -> Evaluator Agent
  -> Engineer Agent
  -> benchmark / tests / git gates
```

The Supervisor should be deterministic application code, not an unrestricted LLM.

## 13. Proposed Agent Responsibilities

### Supervisor

Owns:

- job queue;
- state machine;
- retries;
- resource locks;
- service health;
- SQLite state;
- artifact paths;
- benchmark selection;
- approval gates.

### Video Agent

Can:

- create/run MPT generation jobs;
- start/stop/check required services;
- wait for generation completion;
- collect scene images, MP4 and diagnostics;
- never modify stable code directly.

### Evaluator Agent

Can inspect:

- `precision_diagnostics.json`;
- scene images;
- final video;
- identity consistency;
- continuity;
- factual evidence support;
- visual coherence;
- obvious technical failures.

A local VLM or cloud multimodal model will likely be needed for reliable autonomous visual QA.

### Engineer Agent

Can:

- inspect evaluator findings;
- create a Git worktree / experiment branch;
- edit code only inside the isolated experiment;
- run compile/tests;
- regenerate benchmark(s);
- compare candidate against baseline;
- create a candidate commit/PR.

It must not directly rewrite the stable branch.

## 14. Autonomous Improvement Loop

Target loop:

```text
QUEUE
  -> GENERATE
  -> EVALUATE
      -> PASS -> archive result -> next job
      -> FAIL
          -> classify failure
          -> isolated experiment branch/worktree
          -> patch
          -> compile + tests
          -> benchmark suite
          -> compare against stable
              -> better -> candidate
              -> worse / regression -> discard
```

A single random image must never be enough evidence to conclude a code change improved quality.

## 15. Benchmark Suite Requirement

Before allowing autonomous code promotion, create multiple fixed benchmarks covering at least:

- real product identity;
- unsupported internal mechanism;
- temporal continuity;
- human/character scene;
- environment/landscape;
- generic object without references.

Use repeated seeds or enough repeated runs to distinguish code effects from generative randomness.

## 16. Git Safety Model

Do not let autonomous agents edit the stable working tree directly.

Preferred approach:

```text
stable repo
MPT-worktrees/
  exp-0001/
  exp-0002/
  exp-0003/
```

Candidate promotion gates should include:

```text
compileall PASS
pytest PASS
benchmark suite PASS
no significant quality regression
acceptable runtime / VRAM impact
human review initially
```

No automatic merge to stable until the system has demonstrated reliability over time.

## 17. Agent Factory v0.1 Scope

First version should aim for:

- Python supervisor;
- SQLite database;
- deterministic state machine;
- queue of generation jobs;
- service manager for ports 8080/8090/8188/8501;
- MPT generation tool/API wrapper;
- artifact collector;
- diagnostics parser;
- evaluator interface;
- Git worktree manager;
- test runner;
- Streamlit dashboard on a separate port, e.g. 8600;
- structured logs;
- manual approval for candidate code promotion.

Do not build decorative office/spaceship UI yet. It is presentation only.

## 18. Future Scope

Later:

- local/cloud VLM for visual QA;
- more benchmark types;
- scheduled continuous production;
- automatic candidate PR generation;
- publishing agent for approved TikTok / YouTube Shorts;
- title/description/hashtags;
- platform API integrations;
- optional visual office/spaceship representation of agent state.

## 19. Operating Rules for Future Agents

Before changing code:

1. read this file;
2. inspect current branch and `git status`;
3. inspect latest relevant diagnostics;
4. state the hypothesis being tested;
5. use a worktree/experiment branch for autonomous changes;
6. keep changes topic-agnostic;
7. run focused tests, then broader tests;
8. benchmark against stable;
9. record results;
10. update this file only when the project state meaningfully changes.

Never invent test results, commits, benchmark results or runtime measurements.
