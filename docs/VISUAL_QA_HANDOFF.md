# Visual QA — Windows checkpoint, 2026-10-08

Worktree `D:\Apps\MPT-worktrees\image-model-routing-modernization`, branch `factory/image-model-routing-modernization`. Initial clean local/remote HEAD `87c7ba568b19ed48d041b625f269f5112f0ef4fd`; fetch showed 0/0 divergence. Stable protected HEAD `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.

## Dataset and audit checkpoint

[Dataset](validation/visual-qa-dataset-2026-10-08.json): 16 retained images, 9 reviewed pass, 6 fail, 1 deliberately uncertain. Paths and SHA256 point to local artifacts; do not archive the worktree before preserving them. Labels come from documented assistant visual review, not independent human adjudication. Count follows the original two-hand contract. Images are not versioned.

[Audit](validation/visual-qa-latency-audit-2026-10-08.json): a fresh old QA took 69.169s, including Florence load 7.6192s, post-load caption 2.1642s and LLM HTTP 58.964s. Completion had 1635 tokens and 5642 reasoning characters. Reasoning itself was not saved. [No-thinking probe](validation/visual-qa-fast-judge-probe-2026-10-08.json): HTTP 7.8554s, 191 tokens, no reasoning, same uncertain verdict; later judges repeatedly became unavailable within a 30s timeout. Removing response_format also failed; grammar incompatibility is not established.

Florence CPU provides OCR, detection, grounding and segmented outer shape. It misses exact small-part counts and fused-object identity. The current 8080 server reports vision disabled; no nearby multimodal projector was found. Do not download/reconfigure a heavy model to continue without a separate decision.

At this audit checkpoint implementation/tests remain separate working changes. Zero image-generation requests, GPU benchmarks, retries, dependency changes, service restarts or routing promotion. Next checkpoint records the opt-in implementation and its actual test results.
