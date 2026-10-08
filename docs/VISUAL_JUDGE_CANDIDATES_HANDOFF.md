# Comparative visual judges — preparation, 2026-10-08

## Current closure: full blind QA and factual geometry audited

Execution base06246184eaba9d676706b341b9e3423466e8a709. User kept8080 closed.19 new requests,0 generations: F1 full blind contract on16 original cases givesTP5/TN9/FP0/FN1,0unavailable, mean9.125s/median9.309s,peakglobal7505MiB. Three-hand MPT defect now detected; deformed factual key still accepted. Cold uncertain label remains excluded from binary metrics; OCR brand hallucination persists. G1 separate component-level contract on3 cases flags key but rejects both positives; geometry alone has1 false positive, the other total rejection is a contradictory text status/reason. No label changes or automatic rescue. [Full report](VISUAL_JUDGE_FULL_QA_REPORT.md), [metrics](validation/visual-judge-full-qa-metrics-2026-10-08.json).

No source/weights/dependency/workflow/routing changes; hashes/JSON/diff/secrets checked. Existing58 offline tests are preparation results, not a new pytest. Both own8092 servers closed; stable HEAD/tracked tree unchanged,Comfy queue0/0. Can reopen8080; reserve resources for future inference. F1/G1/previous V2 or ROI timings cannot be merged or compared as causal speedups. F1 uses complete originals/references, blind counts, no ROI, unbounded reason schema; G1 adds generic component comparison requirements only, separate dataset/provenance.

Next: independently review geometry labels and design structured reference/candidate observations separated from verdict. Preserve contradictory/hallucinated evidence as uncertainty; no automatic factual approval. Only then consider explicitly commissioned opt-in evidence/veto integration retaining OCR/deterministic gates/fail-closed. Do not download another model or repeat generations to hide judge errors. Retrieve closing SHA from Git history.

## Current continuation closure: idle controls complete

Execution base9f4296485698bf98539eb284cdec509721a865ee. User closed8080, then game after confirming continuous GPU use. First text control timeout60s under game load is preserved as confounded evidence. New idle run (baseline1000MiB/3% GPU) completes all6 fresh-server controls: text1.199s; positive full2 hands, crop3 incorrectly, full+crop2; negative full/crop3 correctly. Visual HTTP3.725–4.954s for focused counts-only policy, not full QA. Total7 new model requests,5 visual,0 generations, all owned8092 closed. [Report](VISUAL_JUDGE_PREFILL_DIAGNOSIS.md), [idle evidence](validation/visual-judge-prefill-idle-controls-2026-10-08.json).

No source/model/dependency/workflow/routing changes. Existing58 offline tests belong to preparation9f42964; no new pytest claim. The original timeout does not prove a model failure; idle controls do not establish the cause of older ROI timeouts. Do not use crop-only admission: positive crop hallucinates a seconds hand. Next: blind counts within full QA and defective-key/reference control, preserve OCR/fail-closed and existing labels. Backend contrast remains conditional on reproducing failure under idle resources, not a required download now. User may reopen8080/game after this closure; reserve GPU again before further inference. Obtain closing SHA from Git history and confirm origin/status.

## Next phase: prefill controls prepared, GPU execution pending

Continuation base `9bfec74557ba2fa8f1ab19ad2dff462e710e6f63`, clean experimental worktree. User reopened8080 and authorized continuing diagnosis. Readonly checks:8080 health200,8090 root404,8188 system_stats200,Comfy queue0/0,8092 closed. Global VRAM6731/12288MiB, free system RAM7.22GiB: insufficient for the previous full-GPU configuration alongside8080. Asked user to close8080 temporarily via its launcher. Do not kill the shared server or silently switch to partial CPU offload.

Historical V4 log contains `non-consecutive token position` warnings after cancellation and delayed processing. This is a diagnostic observation, not an established cause. New `scripts/diagnose_visual_judge_prefill.py` starts a fresh owned8092 server for EACH request, finally closes only that process, refuses occupied ports/existing evidence and checks model/input hashes. No third model/backend download. Same b11497 runtime and image bounds; counts-only schema, max192 tokens, no target number in the model prompt, no references. These controls intentionally differ from V2/V3/V4 and cannot be merged into their accuracy or latency metrics.

Six predeclared controls: text transport/schema; positive full image; positive crop; positive full+crop; negative full image; negative crop. Positive=valid_cloth_edit, negative=mpt_t2i_text_contract_768. Only preexisting watch regions are used; full/crop views represent the SAME object. These diagnostic crop-only results cannot establish full-scene admission or factual identity. No labels changed. [Offline plan with input hashes](validation/visual-judge-prefill-plan-2026-10-08.json), executed=false. Final58 offline tests passed, exit0,3.40s ([log](validation/visual-judge-prefill-preparation-tests-2026-10-08.txt)); three new tests verify isolation, label/target blinding and input provenance. **Zero new VLM requests so far in this continuation.** Historical42 remain unchanged. No production/default/routing/dependency/workflow changes.

Resume after user closes8080: confirm Git/status/resources/queue, then run:

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -I -B scripts/diagnose_visual_judge_prefill.py --execute --output docs/validation/visual-judge-prefill-controls-2026-10-08.json --log-dir local_image_stack/experiments/bridge/target/visual-judge-prefill-controls-2026-10-08
```

The offline plan filename is different from measured output. Readiness90s/request60s, max6 requests; failed text control aborts visual requests. Each visual failure is retained, not retried. Enforces8080 closed and at least7000MiB free global VRAM before loading. Logs are ignored. Compare observed counts and prefill logs without claiming shape/runtime causality prematurely. If single-image controls fail, stop scope expansion and investigate backend support; a contrasted backend remains pending. Resolve the two baseline false negatives before opt-in admission; retain independent OCR and fail-closed. Closing commit SHA is obtained from Git history, not embedded as a self-reference.

## Current closure — comparative evaluation complete

The user closed8080 and resource clearance was confirmed. Execution base `8ebbb17480f07dd6235ff9b66a65d7dc2a3edbe7`. **Select Qwen3.5-9B Q4_K_M/F16 for the next experimental phase, not automatic admission.** [Full report/matrix](VISUAL_JUDGE_COMPARISON_REPORT.md), [base metrics](validation/visual-judge-baseline-metrics-2026-10-08.json).

V2:16 unique attempts each.9B TP4/TN9/FP0/FN2,0unavailable, mean27.786s/median29.099s, peakglobal10448MiB.8B TP0/TN7/FP0/FN6,3unavailable, mean31.592s/median31.164s, peakglobal11299MiB. Cold expected uncertain excluded from binary confusion;9B called it fail without independent adjudication. Labels remain curated agent reviews.9B still accepts a deformed factual key and MPT three-hand watch; its OCR transcription can hallucinate a brand. No candidate is ready.

V1 exposed underspecified response fields; retained and reinterpreted offline without new requests. V2 uses strict top-level JSON schema, Flash Attention on, min1024/max1536 image tokens.8B temporal cutoff was followed only by its six previously unattempted cases, not retries. V3 blinded counts+ROI+string bounds produced two consecutive60s timeouts for each model; V4 removing maxLength also produced two9B timeouts. Root cause of ROI/prefill failure is unresolved; do not blame grammar alone. Separate protocols and preserve every failure. Total42 attempted VLM requests,0 image generation,0 automatic inference retries.

Final focused tests:55 passed (16 harness +39 QA), exit0,3.33s. [Log](validation/visual-judge-harness-final-tests-2026-10-08.txt). Source changes affect only evaluator/tests/docs, not app/runtime defaults. No global installs, encoder/workflow changes or routing activation. [Closing checks](validation/visual-judge-final-access-2026-10-08.json): own8092 closed,8080 remains closed by user,8090HTTP404,8188HTTP200,Comfy queue0/0, globalVRAM~3970MiB, stable protected HEAD/tracked tree unchanged. The user may reopen their original8080 launcher now.

Next concrete task: diagnose ROI prefill with single-image/text controls and a contrasted backend version, obtain a blind observed count without timeout, then prepare9B as opt-in additional QA evidence with independent OCR/cheap checks. Resolve twoFN before admission; do not activate routing, replace fail-closed, change labels, download a third model or generate new artifacts by inference. Preserve downloaded models/logs/analytical crops under ignored target. For a fresh run choose a new output/log path; existing destinations refuse overwrite. Determine closing SHA via Git history for this handoff; publish normal push only.

The preparation/blocker paragraphs below are historical and superseded by this closure.

Closing evaluator/tests checkpoint: `0452649be06b8a17cb269f4f0d62fbf94bc2be71`. Final evidence/report checkpoint follows; retrieve exact local/remote SHA using Git. No further GPU runs are implicit in this closure.

User explicitly authorized downloading Qwen3.5-9B and Qwen3-VL-8B-Instruct plus their projectors, and a bounded GPU evaluation on the 16 retained images. No image generation, production integration, automatic routing, global dependencies or stable-tree changes are authorized by this evaluation.

Initial local/remote HEAD `b97ec8c101319b42013e6e0f57add791fdf7f064`, clean experimental branch `factory/image-model-routing-modernization`. Fetch:0/0. Stable protected HEAD remains `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.

## Completed preparation

Four public GGUF files downloaded and SHA256/size verified, total12,785,503,168 bytes. [Pinned sources and hashes](validation/visual-judge-candidates-assets-2026-10-08.json), [actual verification](validation/visual-judge-download-verification-2026-10-08.json). Revisions: Qwen official8B `f982a07559d4a2f6c8744d840bf6fccab30eea96`; Unsloth9B `3885219b6810b007914f3a7950a8d1b469d598a5`. Both Apache2.0. Selected ordinary Q4_K_M and matching F16 projectors, not fine-tunes.

Models stored under ignored `local_image_stack\experiments\bridge\target\visual-judge-models`; preserve before archiving this worktree. No weights or ZIPs in Git.

Official portable Windows CUDA12.4 runtime: llama.cpp `b11497`, commit `ff30363a0`, version0.6.0-dev, published2026-10-08. Both release ZIP digests verified. Location: ignored `local_image_stack\experiments\bridge\target\visual-judge-runtime\b11497`. `--version`/`--help` work; supported options include projector, reasoningoff and image token bounds. No global install or changes to current8080 binary. Runtime CUDA12.4 chosen rather than CUDA13.4. Observed NVIDIA driver617.14.

Added `scripts/download_visual_judges.py` (public pinned downloads, partial-file preservation, size/hash validation), `scripts/evaluate_multimodal_judges.py` (owned temporary8092 server, sequential models, label-free prompts, counts derived from observed cardinality, independent geometry/identity/state/progression checks, no inference retries, bounded output/time, globalVRAM samples and finally cleanup of ONLY owned server).

Offline checks:51 tests pass, including12 harness regressions and39 existing visual-QA cases, exit0,4.18s. [Log](validation/visual-judge-harness-tests-2026-10-08.txt). Tests exercise invalid response/counts, disjunction of identity/state and no expected-verdict/review leakage. This is not a model accuracy test. No production code or persisted flags changed. JSON/diff/hashes checked.

## Resource blocker — evaluation not yet performed

Initial GPU11705/12288MiB. Comfy queue0/0; authorized resource preparation sent POST8188/free with unload_models/free_memory true, HTTP200. Comfy remains running; this only unloads cached weights, which reload on a later generation. No supervisor, job, generation or service restart.

After unloading, GPU still~7663MiB used; only~4625MiB remain. Server8080 is still running (PID4080 at inspection), buildb10621, visionfalse. RAM31.77GiB total,6.12GiB free. These conditions do not allow a full GPU comparison of either selected candidate. Heavy CPU offload would change the latency question and consume scarce RAM.

An asynchronous question asks the user to close the existing8080 LLM server temporarily via its window/launcher, leaving Comfy and bridge open, then notify us. Alternative offered: explicitly choose partial CPU offload. Do not infer a choice from silence. Do not kill shared servers or alter startup/configuration to bypass this block. The existing process executable path was unavailable from ordinary inspection; no process arguments or keys were printed. Authentication used for readonly props only stayed in memory.

**Actual comparative GPU requests:0. No candidate chosen.** Do not report either as ready or claim new accuracy/latency results. The user may restart their original8080 launcher after both owned8092 evaluations close.

## Resume after resource clearance

Confirm branch/HEAD/status, fetch divergence, all model hashes,8080 state, GPU/RAM and Comfy queue. Do not rerun downloads when valid files already exist. Keep experimental8092 isolated and use the same policy for both models. Each dataset row includes candidate/full available references, without expected verdict or review reason; no extra image generation.

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -I -B scripts/evaluate_multimodal_judges.py `
  --dataset docs/validation/visual-qa-dataset-2026-10-08.json `
  --manifest docs/validation/visual-judge-candidates-assets-2026-10-08.json `
  --models local_image_stack/experiments/bridge/target/visual-judge-models `
  --server local_image_stack/experiments/bridge/target/visual-judge-runtime/b11497/llama-server.exe `
  --output docs/validation/visual-judge-comparison-2026-10-08.json `
  --log-dir local_image_stack/experiments/bridge/target/visual-judge-evaluation-2026-10-08
```

Fixed initial comparison:context8192, single slot, max768 output tokens, temperature0, reasoningoff, JSONobject, max1536 image tokens/image, HTTPtimeout60s, GPU layers99, native full images capped by token bound. Log actual model placement; do not treat configured GPU layers as measured successful offload. Stop candidate after two consecutive unavailable responses; no inference retries. Output/log destinations refuse overwrite. Global sampled VRAM includes desktop/other processes; not per-model allocation. Record model load time separately; latency includes visual prefill and output. Different runtime/model versions or altered caps require new evidence filenames and explicit labels.

Next deliverable:32-case matrix if both complete, confusion/abstention rates, latency/VRAM, model output audit for three hands/fused keys/temporal state, limitations of curated labels, choice only if evidence warrants it, tests/diff/secrets, checkpoint and normal push. Do not adjust labels/prompts to rehabilitate a preferred model. No automatic routing or pipeline activation follows the comparison.
