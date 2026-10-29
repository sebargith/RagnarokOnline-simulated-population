# M2 - Local inference baseline and operating budget

Status: implementation and measurement in progress; **human conversation quality review is pending**. M3 is outside this work. Results below are development observations until the frozen final run is recorded.

## Starting conditions and decision

On 2026-10-29, PowerShell at `D:\Ragnarok Agents`: clean `main` at `8162e9e`, remote `origin` on GitHub; work uses `codex/m2-inference`. Windows 11 Home Single Language 10.0.26200; Ryzen 9 5900HX, 8 cores/16 threads; 31.86 GiB visible RAM, initially 7.62 GiB available. RTX 3080 Laptop GPU, 16,384 MiB VRAM, NVIDIA driver 591.59; initially 1,348 MiB used. C: 181.78 GiB free, D: 156.86 GiB free (snapshots, not reservations).

Windows Ollama executable: `C:\Users\azusu\AppData\Local\Programs\Ollama\ollama.exe`; CLI and `/api/version` report **0.40.12**. `/api/ps` initially empty. Its startup log confirms `OLLAMA_MODELS=D:/Local_AI/Models/Ollama`, `OLLAMA_NUM_PARALLEL=1`, server context default 32,768, queue default 512, keep-alive 5m, flash attention false, and loopback HTTP on 11434. Request options override the context; the benchmark admits only one request into Ollama, with four waiting locally. No environment variable or global runtime setting was changed.

Inventory also contains several 27B quantizations (~11-13 GB) and two older altered vision models (~5.5 GB each). They were not loaded or benchmarked. Two installed, unmodified Qwen3.5 instruction candidates answer the bounded decision: does a larger, higher-precision model improve short grounded conversation enough to justify its cost? No download, move, upgrade, third model or paid inference is needed.

| Candidate | API artifact size | Parameters / quantization | Reason |
| --- | ---: | --- | --- |
| `qwen3.5:4b` | 3,324,173,934 bytes (3.10 GiB) | 4.2B / Q4_K_M | Smaller baseline, lower memory and latency |
| `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K` | 8,876,985,279 bytes (8.27 GiB) | 9.2B / Q6_K | Existing larger, higher-precision alternative |

Exact API digests are pinned in [candidate configuration](../../config/m2-candidates.json). Local manifests include model tensor blobs `sha256:a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50` (4B, 2,648,593,216 bytes) and `sha256:073a9275e65d9c8cd2819cf5f77b99fbaa6e87ba591da6bbaa86ec073a64bfef` (9B, 7,958,818,848 bytes). Artifact sizes include vision/projector metadata/assets; requests are text only. These are content-addressed manifest references, not a fresh hash of every multi-GB weight file.

## Harness and methodology

[Fixtures](../../fixtures/m2-scenarios.json), [inference boundary](../../inference/m2.py), [driver](../../scripts/bench_m2.py), and [boundary tests](../../tests/test_m2.py) are M2 benchmark code. They do not implement persistent agents or dispatch game actions. Five identities each receive only their own system prompt, memory and two-turn conversation. The global fixture inventory remains outside the model request. Subsequent recall/action fixtures reset the conversation history. There is no session ID or shared message array passed into Ollama; each request carries a complete scoped prompt. A secret marker check supplements, but does not prove, semantic isolation.

Each identity runs five requests: two linked conversation turns, structured recall, a valid adjacent move proposal, and an injection/disconnected/stale-state proposal. Recall tests a friend, a commitment, a witnessed loan, an unverified rumor, an unknown movement outcome, and unknown inventory. The strict recall score checks exact normalized field values; a paraphrase can fail even when factually similar. Action proposals pass a separate schema/current-state/epoch/adjacency validator against simulated fixture state and are **never executed**. M1 retains ownership of actual game state and action validation.

Profiles are synchronized bursts of 1, 3 or 5 isolated identities per turn, serialized through one FIFO inference slot and at most four waiting slots. There is at most one outstanding request per identity. Three independent repetitions use seeds 42/43/44. Cold profiles start with the model unloaded and `/api/ps` empty; only the first request actually loads the runner. Later requests in a cold profile include queueing behind that load or use the loaded runner. This is **runner-cold**, with normal Windows file cache; no reboot, cache flush, or disk-cold claim. Warm profiles start after an excluded, separately recorded priming request. Every profile unloads afterward. Raw `load_duration` distinguishes actual loads from later requests.

TTFT is time from HTTP dispatch to the first nonempty **visible** content chunk. Service latency ends at the final `done` chunk; queue delay is local admission to dispatch; response latency includes queue plus service. Runtime-internal scheduling/processing is inside service latency and is not separately inferred as queue delay. Ollama's final frame supplies input/output tokens and load/prompt/generation durations. Summaries retain n, mean, sample standard deviation, median, nearest-rank p95, and maximum. Request failures have unknown token usage unless the final frame arrived; successful-request token sums are not a bill for failed attempts.

Native Windows memory counters and `nvidia-smi` are sampled about once per second throughout load/prime/request/unload. Record total system physical memory used/available, summed Ollama working sets and private commit, summed M1 working sets, and total device VRAM use. Working sets may double-count shared pages; private commit is not resident RAM; GPU totals include desktop/other users. Sampled peaks may miss subsecond spikes. Both OpenKore test clients remain connected beside MariaDB/rAthena; a read-only thread records snapshot gaps/disconnections. This measures idle M1 coexistence, not active combat or a graphical client.

Streaming uses absolute deadlines, a socket watchdog, bounded response bytes/content, and no retry. A transport/deadline/resource failure stops further dispatch rather than placing another request behind possibly unfinished work. Prompts have a character admission cap; actual token counts are recorded. A 2,048-token context is an allocation ceiling, not a claim that long contexts have passed these short fixtures. Gameplay fallback and live action rechecks remain M3 integration work.

The HTTP streaming metrics, `think`, `format`, context and unload controls follow [Ollama chat API](https://docs.ollama.com/api/chat), [thinking controls](https://docs.ollama.com/capabilities/thinking), and [FAQ](https://docs.ollama.com/faq); tested local behavior/version is authoritative for these results.

## Development experiments

- `runtime/evidence/20261029T172253Z-m2-pilot/`: 20 measured requests, 2 excluded priming requests, one repetition, profile 1 only. Warm service mean 0.478s (4B) / 0.841s (9B), first load 7.67s / 8.38s. No transport/check failure in 12 automated cases. Peak total GPU 9,565 MiB, minimum available RAM 5.73 GiB. Both M1 clients remained connected, maximum gap 1.032s. This predates the absolute socket watchdog and fixed final settings; source hashes are retained in its manifest.
- First unit run: a fake transport indexed an empty prompt in the ownership-release test; fixed the test input. All 15 current boundary tests subsequently passed, including a trickling-stream absolute-deadline check.
- `runtime/evidence/20261029T172447Z-m2-capacity-pilot/`: initial 3/5-session development run uses unconstrained JSON and inherited 4B presence penalty 1.5. It exposes prose/fenced JSON, noncanonical recall values and safe but incorrect no-op proposals, which the validator rejects. It cannot establish final comparable quality. The final revision explicitly sets presence/frequency penalties to zero for both candidates, and uses schemas for recall/actions while leaving dialogue unconstrained. Raw failures are retained locally; no score is silently converted into success.
- That capacity pilot completed 160 measured requests / 4 excluded primes: 38/96 strict automated checks failed, zero transport failures. Minimum available RAM 4.80 GiB, peak GPU 9,573 MiB; both clients stayed connected with 1.032s maximum snapshot gaps.
- `runtime/evidence/20261029T172855Z-m2-normalized-pilot/`: 100 measured requests / 2 excluded primes, five-session cold/warm, one repetition with normalized sampling and structured schemas. 4B fails 10/30 strict checks (lost meeting timing or safe but incorrect no-op); 9B passes 30/30. Warm response p95: 3.547s / 6.391s. This justifies keeping both for the fixed final comparison and preferring 9B for further technical evaluation; no third candidate is warranted.

Development and final requests/priming token totals will be reported separately. Codex development-token accounting is not available to this harness.

## Frozen acceptance limits

[Machine-readable limits](../../config/m2-limits.json) are to be committed **before** the final run. Neither performance thresholds nor output fixtures may change during that run. Final sampling: both candidates, profiles 1/3/5, cold/warm, three repetitions, five requests per identity = **270 measured requests per candidate, 540 total**, plus 18 excluded warm priming requests.

Both models use context 2,048, output cap 160, temperature 0.7, top-p 0.8, top-k 20, min-p 0, repeat penalty 1.05, presence/frequency penalties 0, thinking disabled, keep-alive 5m. Full sampling settings are recorded per run. Limits: one active call, four queued, zero retries, one outstanding request per identity, 5,000 prompt characters, 65,536 streamed bytes, 4,096 visible output characters. Hard service timeouts are 20s warm/60s first cold; admission-to-completion deadlines 45s/100s. These are fault ceilings, distinct from the lower latency targets.

Per profile, warm p95: visible TTFT <=1s, service <=3s, queue <=6s, response <=8s. First cold visible TTFT <=15s; every cold-profile response <=20s. Zero transport failures, truncations, foreign private-marker leaks, monitor errors or disconnected M1 snapshots; M1 maximum snapshot gap <=2.5s. Per-model exact recall and valid-action agreement >=95%; every injection case must select `none`. Resource guard: minimum available physical RAM >=2 GiB and total GPU use <=14 GiB (14,336 MiB). No target may be relaxed after a failed run without a recorded decision and separate run.

Model selection and final measurements remain pending. Human review must assess naturalness, grounding, believable continuity, unsupported action/outcome claims and identity leakage; automated checks do not complete it.
