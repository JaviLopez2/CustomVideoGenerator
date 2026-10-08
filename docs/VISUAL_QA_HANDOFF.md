# Visual QA — Windows checkpoint, 2026-10-08

Worktree `D:\Apps\MPT-worktrees\image-model-routing-modernization`, branch `factory/image-model-routing-modernization`. Initial clean local/remote HEAD `87c7ba568b19ed48d041b625f269f5112f0ef4fd`; fetch showed 0/0 divergence. Stable protected HEAD `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.

## Dataset and audit checkpoint

[Dataset](validation/visual-qa-dataset-2026-10-08.json): 16 retained images, 9 reviewed pass, 6 fail, 1 deliberately uncertain. Paths and SHA256 point to local artifacts; do not archive the worktree before preserving them. Labels come from documented assistant visual review, not independent human adjudication. Count follows the original two-hand contract. Images are not versioned.

[Audit](validation/visual-qa-latency-audit-2026-10-08.json): a fresh old QA took 69.169s, including Florence load 7.6192s, post-load caption 2.1642s and LLM HTTP 58.964s. Completion had 1635 tokens and 5642 reasoning characters. Reasoning itself was not saved. [No-thinking probe](validation/visual-qa-fast-judge-probe-2026-10-08.json): HTTP 7.8554s, 191 tokens, no reasoning, same uncertain verdict; later judges repeatedly became unavailable within a 30s timeout. Removing response_format also failed; grammar incompatibility is not established.

Florence CPU provides OCR, detection, grounding and segmented outer shape. It misses exact small-part counts and fused-object identity. The current 8080 server reports vision disabled; no nearby multimodal projector was found. Do not download/reconfigure a heavy model to continue without a separate decision.

At this audit checkpoint implementation/tests remain separate working changes. Zero image-generation requests, GPU benchmarks, retries, dependency changes, service restarts or routing promotion. Next checkpoint records the opt-in implementation and its actual test results.

## Implementation checkpoint

Dataset/audit commit `1ec050a9b5dc2268dbf5a501b4b4fb663c659019`. Implemented `app/services/visual_qa.py`, scoped private MPT integration, bounded local judge transport, offline retained-artifact evaluator and 39 new test cases. No persisted flags enabled. Experimental private caller needs both boolean `openai_image_visual_qa_experimental_enabled=True` and explicit `scene_qa_contracts`; normal callers retain their existing QA.

Critical factual references/continuity automatically require identity evidence that this caption/mask engine cannot establish, so remain uncertain and rejected. Empty contracts retain the existing Klein gate. Temporal requirements cannot be bypassed by count-only contracts. No retries or cross-model rehabilitation. A direct dataset pass is not full pipeline/continuity certification.

Final test run: **387 passed, 17 subtests passed, 1 integration test skipped**, exit 0, 15.12s. [Log](validation/visual-qa-final-tests-2026-10-08.txt). Includes all previous 241 cases unchanged, 39 new visual QA cases and 107 additional LLM cases. One existing Starlette/httpx deprecation warning; no dependency installation.

Final dataset: **3/16 decided**, TP1/TN2/FP0/FN0, uncertain13, unavailable0. Mean4.5073s, median4.2692s, max9.7788s; no p95 claimed. The absence of false verdicts on only three decisions does not establish classifier reliability. Use [final results](validation/visual-qa-final-results-2026-10-08.json), not pre-parser intermediate runs.

## Closure and recovery

Implementation commit `d8de6a5195eecb6db6e242736fc4d5e89509d0ab`. Read [full report and regression matrix](VISUAL_QA_REPORT.md). Obtain final local/remote SHA using Git rather than an impossible self-referential document hash. Final documentation checkpoint contains matrix, intermediate evidence, final access checks, reports and all updated handoffs. Publish by normal push on the experimental branch only, check 0/0 divergence and clean worktree.

Run evaluator without generation:

```powershell
$env:PYTHONPATH = (Get-Location).Path
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B scripts/evaluate_visual_qa.py --dataset docs/validation/visual-qa-dataset-2026-10-08.json --output local_image_stack/experiments/bridge/target/qa-next-results.json
```

It refuses to overwrite evidence. `--legacy-fast` invokes the local text judge and may time out; do not run repeated calls without a concrete latency hypothesis. Main result is direct engine QA, not end-to-end rendering. Preserve target/autonomous-2026-10-08, target/resolution-details-2026-10-07, root/single-ref artifacts and Comfy input references before moving/archiving.

Tests: from this worktree, `MPT_RUN_INTEGRATION_TESTS=0`, Python `-B -m pytest -q` on the paths in `docs/validation/visual-qa-final-tests-2026-10-08.txt` / this checkpoint's report. The exact reproducible suite command is in the report. Set `MPT_KLEIN_BRIDGE_BIN` to `local_image_stack\experiments\bridge\target\debug\klein4b-experimental-bridge.exe` for existing Rust bridge tests. No GPU/downloads needed; do not install global dependencies.

Closing health:8080 200,8090 404,8188 200; Comfy queue0/0;8091 not started. Factory/runs and19 log files readable; only1024 bytes read to verify access, no log contents printed. Stable tracked files unchanged, HEAD protected; untracked backups remain. [Access record](validation/visual-qa-final-access-checks-2026-10-08.json).

Next justified work: stronger visual extractor/judge for internal structure/count and temporal state on this dataset, independent label review, and diagnosis of bounded judge latency. Existing text-only endpoint cannot supply missing visual evidence. A heavyweight model/download/dependency or server change needs a separate decision; no automatic promotion, three-reference test or new image generation follows this checkpoint.

## Subsequent authorized candidate preparation

The user authorized download and bounded GPU evaluation of Qwen3.5-9B and Qwen3-VL-8B-Instruct. Four model/projector GGUFs and a portable official CUDA runtime are downloaded/hash verified;51 offline QA/harness tests pass. Evaluation remains pending GPU/RAM clearance:8080 LLM remains resident, GPU~7663MiB used after Comfy cached weights were unloaded, RAM~6.12GiB free. Read [current candidate handoff](VISUAL_JUDGE_CANDIDATES_HANDOFF.md) before proceeding. No comparative inference has been run and no candidate is selected.

## Subsequent comparison closure

User closed8080; the resource blocker above is resolved.42 bounded VLM attempts, zero generation. V2 matrix16 cases/model:9B detects4/6 negatives, accepts9/9 positives, mean27.786s and peakglobal10448MiB;8B detects0/6 negatives, accepts7/9 positives with3timeouts, mean31.592s and peak11299MiB. Select9B for next experimental work only; two dangerousFN and ROI/prefill timeouts remain.55 focused tests pass, exit0; no productive/default/routing changes. Own8092 closed, user can reopen8080. [Report](VISUAL_JUDGE_COMPARISON_REPORT.md) and [current recovery handoff](VISUAL_JUDGE_CANDIDATES_HANDOFF.md) supersede preparation status.
