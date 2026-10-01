# Evidence, continuity and retry — final recovery 2026-10-01

## Recovery and Git

Worktree: `/workspace/scratch/845a021772d1/mpt-evidence-fix`.
Branch: `factory/evidence-continuity-fix`.
Base and starting HEAD: `188001bf82fee2518002c9105dec77c4a49cb573`, published
`factory/narration-timeline`. The older local narration commit `a4fc2f18339e411b6d453034d937c43893c03a08`
has an identical tree. Stable remains clean at `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.
Factory source is unchanged.

At continuation, the environment did NOT contain the evidence worktree, branch,
reflog entries or last test log. Searches of the available workspace and /tmp found
no alternate copy. The same worktree/branch was restored from the published base
and the exact source/test edits recorded in this conversation. No existing correct
working tree was discarded. The last two recorded edits were documentation:
`AGENT_FACTORY_STATE.md` and this handoff. They were complete except for the pending
full-suite result; there were no hidden narration/identity code changes in those
two edits. Their content is restored here with current validation and recovery facts.

The previous 40/358 test counts are historical, not the validation of this delivery.
The prior full run ended with 94 failed, 1059 passed, 19 skipped, 9 warnings,
17 errors, 8617 subtests passed in 72.20s, including missing streamlit-tour. The
result of the interrupted rerun is unavailable and is not asserted.

## Final behavior

1. `llm._scene_reference_coverage` correctly rejected unsupported mechanisms, but
   `generate_scene_image_plan` then reused the rejected item's `safe_visual_alternative`.
   The deterministic gate now discards that alternative and unsafe subject/features,
   query, identity hint/guard and continuity metadata before prompt construction.
   A primary-subject scene can retain relevance through the subject of an earlier
   covered external identity scene, using its manual identity evidence for a closed
   exterior view. This final refinement avoids needless generic imagery when evidence
   already exists; it never copies the rejected action or applies primary references
   to outputs/secondary entities. Without that evidence, a conservative context is
   used. Coverage status still records the original rejection for diagnosis.
2. Planner instructions and `_qwen_precision_prompt_with_references` treated too
   much of the previous frame as persistent. Prompts now preserve only intended target
   identity/content and narrated state; incidental props, alternate subjects and text
   may be removed. The on-demand loop applies that contract to Standard roots too.
   Existing grouping, chain resets, reference selection and combined continuity +
   stable primary identity anchor remain. The existing text audit also checks adjacent
   contradictions and unsupported externalization of internal processes. No extra pass.
3. The direct Qwen loop previously accepted the last valid attempt unconditionally.
   `_select_duplicate_correction` now selects the retry only when its existing cheap
   dHash similarity is strictly lower. Worse/equal, missing metric, empty or technically
   invalid correction retains the valid original. No third attempt, candidate search
   or new evaluator. `scenes[].corrective_retry_selection` exposes original_metric,
   retry_metric, selected_candidate and reason. Selected QA, render and next continuity
   source all use the selected image. Normal scenes still generate once.

## Precision ratio

`task._apply_openai_image_precision_budget` applies a soft planning ceiling:
ceil(9 * .65) = 6, with an explicit exception for reference-critical scenes.
Five planned Precision scenes remain five. Later the on-demand loop explicitly
promotes usable continuity references to Precision (`continuity_edit_chain`) without
reapplying that ratio. Two promotions explain 5 -> 7 (77.8%). No global hard cap
is added. Quality/continuity takes priority; 20 steps and one normal candidate remain.
Two Standard requests become reference edits, not two extra scenes. Precision scene
count rises 40% relative to five; this is NOT a total-time/cost estimate. Actual
overhead requires per-attempt generation_seconds and retry counts from artifacts.

## Environment

`MPT-Agent-Factory/.venv/bin/python` was restored as a symlink to
`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12`.
The previous environment restoration had lost the target link while leaving
python3/python3.12 links pointing at it. This is inside Factory's ignored `.venv`,
outside the MPT worktree, untracked, and intentionally retained for local testing.
It is not part of the deliverable and may need repair after another environment reset.

fastapi 0.136.3 and streamlit-tour 1.1.0 were already in MPT's pyproject.toml but
missing from this venv. They were installed locally, along with the already-declared
redis 5.2.0 and python-multipart 0.0.27 (replacing local 0.0.32). annotated-doc 0.0.5
was installed transitively. No requirements, pyproject, lockfile or other dependency
manifest changed. Python used: 3.12.14. No services were started or restarted.

## Final tests after source changes

Run from the evidence worktree. Exact common prefix:

```bash
MPT_RUN_INTEGRATION_TESTS=0 /workspace/scratch/845a021772d1/MPT-Agent-Factory/.venv/bin/python -m pytest -q
```

Specific arguments:
```text
test/services/test_corrective_continuity.py test/services/test_qwen_quality_v31.py
```
Result: **43 passed in 1.63s**.

Affected-area arguments:
```text
test/services/test_corrective_continuity.py test/services/test_qwen_quality_v31.py test/services/test_narration_timeline.py test/services/test_task.py test/services/test_voice.py test/services/test_subtitle.py test/services/test_material.py test/services/test_material_openai_image.py test/services/test_llm.py
```
Result: **359 passed, 7 skipped, 2 warnings, 42 subtests passed in 5.04s**.

Full-suite argument: `test`.
Result: **1142 passed, 19 skipped, 9 warnings, 8631 subtests passed in 142.14s (0:02:22)**.
Exit code 0. No failures remain in this run. Full-suite warnings additionally cover
MoviePy/NumPy deprecation and existing Pydantic enum serialization in settings tests.

Warnings in the affected suite are audioop deprecation (pydub) and Starlette's httpx
test-client deprecation. Specific regressions cover hostile fallback alternatives,
reuse of covered identity without mechanism leakage, combined anchors, .97 -> .98,
.97 -> .80, equality, missing metric, empty/invalid correction, disabled retry,
selected continuity output and Balanced defaults. All generation/render calls in
these tests are mocked. No actual Polaroid/Qwen/ComfyUI run is claimed.

## Diff review and limits

Only llm.py, material.py, their regression tests and these two state documents change.
No task.py/narration.srt logic, dependency files, services, bridge, Factory source,
reference selector or heavyweight model is changed. No topical rules are added.
No temporary file or symlink is staged. The complete source/test/documentation diff
was reviewed; `git diff --check` passed. Stable MPT and Factory both have clean
`git status --short --branch`. Final tests above ran after the last source edit;
only documentation of the results followed. No old result is substituted for them.

Prompt constraints cannot guarantee a model removes every accidental background
object. A generic context remains when independent evidence is unavailable. dHash
measures structural similarity, not factual truth. Windows-native and visual
validation remain for the user; offline tests do not establish improved video quality.

## Next manual benchmark — not executed here

Repeat the controlled SX-70 benchmark once against this isolated branch, keeping
the exact seven-paragraph script, six original references/descriptions/roles and
Balanced settings from successful job `15825038-3597-4b77-85ee-0b9f0a9a5c27`.
First run the tests on Windows. Use a separate Factory config with `[mpt].root`
pointing to the evidence worktree and `[mpt].branch='factory/evidence-continuity-fix'`.
Use exactly one supervisor with the same config, not the stable MPT worktree.

```powershell
Set-Location 'D:\Apps\MPT-Agent-Factory'
.\.venv\Scripts\python.exe .\scripts\queue-polaroid.py --config .\factory-evidence.toml --references 'D:\Refs\SX70'
.\.venv\Scripts\python.exe -m mpt_factory --config .\factory-evidence.toml supervisor
```

Replace only the reference directory if the six originals live elsewhere. Success:
9 semantic scenes with internal narration.srt and subtitles still false; no rejected
mechanism in fallback prompts; scene 4 uses observable evidence rather than exposed
invented mechanics; scene 5 and later retain intended output content while avoiding
incidental background subjects; reintroduced primary identity matches its stable
anchor. Any corrective retry must improve similarity or retain the original. No
third attempt. Record effective routes, not an artificial exact .65 requirement.

Return request/snapshot, provenance, narration.srt, material_sources.json,
precision_diagnostics.json, worker/supervisor logs, all retained scene images and
final MP4. Compare generation_attempts, corrective_retry_selection, continuity source,
references/roles, prompts and generation_seconds. Lost identity/content, unsupported
mechanisms, accepted worse metrics, extra attempts or lost semantic timeline are
regressions. Background hygiene requires visual inspection as well as prompt review.
