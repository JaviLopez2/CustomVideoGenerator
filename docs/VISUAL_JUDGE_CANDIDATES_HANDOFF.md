# Comparative visual judges — preparation, 2026-10-08

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
