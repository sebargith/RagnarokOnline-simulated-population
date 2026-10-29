# M2 - Local inference baseline and operating budget

Status: **the 9B configuration passes the frozen automated M2 targets; human conversation quality review and coordinator acceptance are pending**. M3 was not started. The 4B baseline fails the fixed suitability criteria.

## Starting conditions and decision

On 2026-10-29, PowerShell at `D:\Ragnarok Agents`: clean `main` at `8162e9e`, remote `origin` on GitHub; work uses `codex/m2-inference`. Windows 11 Home Single Language 10.0.26200; Ryzen 9 5900HX, 8 cores/16 threads; 31.86 GiB visible RAM, initially 7.62 GiB available. RTX 3080 Laptop GPU, 16,384 MiB VRAM, NVIDIA driver 591.59; initially 1,348 MiB used. C: 181.78 GiB free, D: 156.86 GiB free (snapshots, not reservations).

Windows Ollama executable: `C:\Users\azusu\AppData\Local\Programs\Ollama\ollama.exe`; CLI and `/api/version` report **0.40.12**. `/api/ps` initially empty. Its startup log confirms `OLLAMA_MODELS=D:/Local_AI/Models/Ollama`, `OLLAMA_NUM_PARALLEL=1`, server context default 32,768, queue default 512, keep-alive 5m, flash attention false, and loopback HTTP on 11434. Request options override the context; the benchmark admits only one request into Ollama, with four waiting locally. No environment variable or global runtime setting was changed.

Inventory also contains several 27B quantizations (~11-13 GB) and two older altered vision models (~5.5 GB each). They were not loaded or benchmarked. Two installed Qwen3.5 instruction candidates answer the bounded decision: does a larger, higher-precision model improve short grounded conversation enough to justify its cost? No download, move, upgrade, third model or paid inference was needed.

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

Streaming uses absolute deadlines, a socket watchdog, bounded response bytes/content, and no retry. A transport/deadline failure opens the inference circuit and stops subsequent dispatch. The resource monitor stops new admissions when its guard trips; an already admitted burst can finish before the next admission check (at most five requests). No guard tripped in the final run. Prompts have a character admission cap; actual token counts are recorded. A 2,048-token context is an allocation ceiling, not a claim that long contexts have passed these short fixtures. Gameplay fallback and live action rechecks remain M3 integration work.

The HTTP streaming metrics, `think`, `format`, context and unload controls follow [Ollama chat API](https://docs.ollama.com/api/chat), [thinking controls](https://docs.ollama.com/capabilities/thinking), and [FAQ](https://docs.ollama.com/faq); tested local behavior/version is authoritative for these results.

## Development experiments

- `runtime/evidence/20261029T172253Z-m2-pilot/`: 20 measured requests, 2 excluded priming requests, one repetition, profile 1 only. Warm service mean 0.478s (4B) / 0.841s (9B), first load 7.67s / 8.38s. No transport/check failure in 12 automated cases. Peak total GPU 9,565 MiB, minimum available RAM 5.73 GiB. Both M1 clients remained connected, maximum gap 1.032s. This predates the absolute socket watchdog and fixed final settings; source hashes are retained in its manifest.
- First unit run: a fake transport indexed an empty prompt in the ownership-release test; fixed the test input. All 15 current boundary tests subsequently passed, including a trickling-stream absolute-deadline check.
- `runtime/evidence/20261029T172447Z-m2-capacity-pilot/`: initial 3/5-session development run uses unconstrained JSON and inherited 4B presence penalty 1.5. It exposes prose/fenced JSON, noncanonical recall values and safe but incorrect no-op proposals, which the validator rejects. It cannot establish final comparable quality. The final revision explicitly sets presence/frequency penalties to zero for both candidates, and uses schemas for recall/actions while leaving dialogue unconstrained. Raw failures are retained locally; no score is silently converted into success.
- That capacity pilot completed 160 measured requests / 4 excluded primes: 38/96 strict automated checks failed, zero transport failures. Minimum available RAM 4.80 GiB, peak GPU 9,573 MiB; both clients stayed connected with 1.032s maximum snapshot gaps.
- `runtime/evidence/20261029T172855Z-m2-normalized-pilot/`: 100 measured requests / 2 excluded primes, five-session cold/warm, one repetition with normalized sampling and structured schemas. 4B fails 10/30 strict checks (lost meeting timing or safe but incorrect no-op); 9B passes 30/30. Warm response p95: 3.547s / 6.391s. This justifies keeping both for the fixed final comparison and preferring 9B for further technical evaluation; no third candidate is warranted.

Development and final requests/priming token totals will be reported separately. Codex development-token accounting is not available to this harness.

## Frozen acceptance limits

[Machine-readable limits](../../config/m2-limits.json) were committed and pushed as **`be52a30` before** the final run. Neither performance thresholds nor output fixtures changed during that run. Final sampling: both candidates, profiles 1/3/5, cold/warm, three repetitions, five requests per identity = **270 measured requests per candidate, 540 total**, plus 18 excluded warm priming requests.

Both models use context 2,048, output cap 160, temperature 0.7, top-p 0.8, top-k 20, min-p 0, repeat penalty 1.05, presence/frequency penalties 0, thinking disabled, keep-alive 5m. Full sampling settings are recorded per run. Limits: one active call, four queued, zero retries, one outstanding request per identity, 5,000 prompt characters, 65,536 streamed bytes, 4,096 visible output characters. Hard service timeouts are 20s warm/60s first cold; admission-to-completion deadlines 45s/100s. These are fault ceilings, distinct from the lower latency targets.

Per profile, warm p95: visible TTFT <=1s, service <=3s, queue <=6s, response <=8s. First cold visible TTFT <=15s; every cold-profile response <=20s. Zero transport failures, truncations, foreign private-marker leaks, monitor errors or disconnected M1 snapshots; M1 maximum snapshot gap <=2.5s. Per-model exact recall and valid-action agreement >=95%; every injection case must select `none`. Resource guard: minimum available physical RAM >=2 GiB and total GPU use <=14 GiB (14,336 MiB). No target may be relaxed after a failed run without a recorded decision and separate run.

## Final run and selection

Run **`20261029T173111Z-m2-acceptance`**, tested source **`be52a3022ab08a0f3e2cd1d25b282323f783f50c`**. [Machine-readable results](M2-results.json) retain source/raw-file SHA-256 values, exact artifacts, sampling/configuration, all per-profile statistics, per-repetition resource peaks, loaded-runner reports and every frozen-target outcome. Raw prompts/responses/resource samples/priming/manifest remain ignored at `D:\Ragnarok Agents\runtime\evidence\20261029T173111Z-m2-acceptance\`. The exporter verifies the recorded source hashes before using the fixtures to render samples.

**Provisional technical selection: `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K`.** [Operating configuration](../../config/m2-operating.json) carries its pinned digest and the measured context/output/queue/deadline/sampling limits. It passes every fixed automated criterion. The smaller model is faster but does not meet the contract; retaining it as the default would sacrifice required recall and useful bounded proposals. No third candidate is justified by a remaining capacity gap. This selection does not approve dialogue quality or authorize M3.

### Warm profiles

Seconds; all are p95 except the last column. Each row has three repetitions; n counts requests across all five cases and identities. Standard deviation is for full response time. Full means, standard deviations, medians, p95 and maxima for every metric, including token counts, are in the JSON.

| Model | Sessions | n | Visible TTFT | Service | Queue | Response | Response SD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4B | 1 | 15 | 0.156 | 1.109 | 0.000 | 1.109 | 0.341 |
| 4B | 3 | 45 | 0.219 | 1.438 | 2.485 | 3.047 | 0.931 |
| 4B | 5 | 75 | 0.219 | 1.812 | 3.813 | 4.891 | 1.542 |
| 9B | 1 | 15 | 0.375 | 1.657 | 0.000 | 1.657 | 0.465 |
| 9B | 3 | 45 | 0.359 | 1.672 | 3.250 | 4.844 | 1.265 |
| 9B | 5 | 75 | 0.313 | 1.594 | 4.766 | 6.360 | 1.920 |

### Cold profiles

Three actual runner loads per row. Each cold profile starts unloaded; later requests can wait behind the load. A p95 over all requests in a five-session profile can hide the three actual cold starts, so the first-request maximum and nine-load statistics are reported explicitly.

| Model | Sessions | n | Response p95 (s) | Response max (s) |
| --- | ---: | ---: | ---: | ---: |
| 4B | 1 | 15 | 5.359 | 5.359 |
| 4B | 3 | 45 | 6.078 | 6.500 |
| 4B | 5 | 75 | 7.234 | 9.625 |
| 9B | 1 | 15 | 9.828 | 9.828 |
| 9B | 3 | 45 | 11.375 | 11.766 |
| 9B | 5 | 75 | 11.813 | 12.860 |

4B first-cold visible TTFT maximum: **5.109s**; nine load durations mean **3.433s**, sample SD **0.564s**, maximum **4.897s**. 9B: first-cold visible TTFT maximum **9.235s**; nine load durations mean **8.529s**, sample SD **0.249s**, maximum **8.759s**. All cold targets passed for both models. This is not a Windows-disk-cold measurement.

### Agreement, usage and resources

| Model | Exact recall | Valid-move agreement | Injection selects none | Truncated replies | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4B | 28/54 | 10/54 | 54/54 | 8 | 69,690 / 10,666 |
| 9B | 54/54 | 54/54 | 54/54 | 0 | 67,882 / 8,446 |

**Zero transport failures and zero foreign private-marker matches across 540 measured requests.** 4B's 70 strict check failures include lost meeting timing and safe but incorrect no-op proposals; eight additional conversation replies hit the cap. One repeated truncated pattern also exposes its own private keepsake; that is outside the foreign-marker metric and is visible in the review set. 9B passes all 162 structured checks. Structured decoder constraints help with syntax; they do not establish factual or social quality. The injection fixture is narrow and does not prove general jailbreak resistance.

Total final measured usage: **137,572 input / 19,112 output tokens**. Eighteen excluded warm-up requests add **288 / 45** tokens. Development is separate: 280 measured requests, **70,034 / 9,224** tokens; eight priming requests add **128 / 38**. These are runtime-reported counts, not Codex-development accounting or a capacity estimate for longer memories. Final prompts used at most **414 input tokens** (4B) / **289** (9B); generation reached 160 / 65 respectively. Long-context performance remains unverified.

| Sampled resource | 4B phases | 9B phases |
| --- | ---: | ---: |
| Samples | 228 | 382 |
| Peak total device VRAM | 5,642 MiB | 9,952 MiB |
| Minimum available system RAM | 5.75 GiB | 5.19 GiB |
| Peak summed Ollama working set | 2.07 GiB | 2.95 GiB |
| Peak summed Ollama private commit | 6.68 GiB | 11.80 GiB |

There are **611 total resource samples**, including the initial baseline sample. Peak system physical RAM used was **26.66 GiB**; peak summed M1 working set **656.36 MiB**. Both M1 clients produced **660 connected snapshots each**, no disconnected samples; maximum gaps **1.032s / 1.047s**. No monitor errors or resource guard trips. These sampled peaks include background desktop load and exclude no other apps. All M1 processes were stopped cleanly afterward, all six M1 listeners were absent, and Ollama `/api/ps` was empty. The Ollama app/store remain in place.

The runtime log records eight inference/batch threads, 34/34 layers offloaded for 9B, a 64 MiB CUDA KV buffer, context 2,048, one slot, and effective `flash_attn=auto` (distinct from the startup environment flag). Per-phase `/api/ps` records equal loaded size/VRAM size for both candidates; its 9B quantization field says `unknown`, while the pinned artifact and `/api/show` identify Q6_K. [Results](M2-results.json) include SHA-256 hashes of the Ollama host and llama-server launcher. Backend DLLs were not separately hashed; version 0.40.12, hardware/driver and runtime evidence define the tested installation.

## Human review and remaining acceptance

[Conversation samples](M2-conversations.md) show every identity in the five-session warm repetition 0 for both candidates, plus all failure/truncation patterns grouped by exact output with occurrence counts. The review is **pending**. Known issues to judge include 9B replies saying a borrowed potion "helped" without a supplied consumption/result event, treating a walk timeout as a connection timeout, and sometimes assuming the current location is the future meeting gate. Automatic recall success does not excuse unsupported claims in dialogue.

The single next action is the user's quality review with the coordinator, including these grounding issues and the provisional 9B operating budget. Keep M2 unaccepted until that review is recorded. Request a specific M2 repair if needed; do not start M3. No three/five game agents, persistent memory, live LLM action dispatch or gameplay fallback have been implemented here.

## Commands actually run

PowerShell 7 at `D:\Ragnarok Agents`, Python 3.11.9 in the existing `.venv`; reuse the prepared M1 installation and existing pinned Ollama assets. No installation command is implied.

```powershell
& .\.venv\Scripts\python.exe scripts/m1.py start
& .\.venv\Scripts\python.exe scripts/m1.py client agent
& .\.venv\Scripts\python.exe scripts/m1.py client peer
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m py_compile inference/m2.py scripts/bench_m2.py
& .\.venv\Scripts\python.exe scripts/bench_m2.py --profiles 1 --repeats 1 --label pilot
& .\.venv\Scripts\python.exe scripts/bench_m2.py --profiles 3 5 --repeats 1 --label capacity-pilot
& .\.venv\Scripts\python.exe scripts/bench_m2.py --profiles 5 --repeats 1 --label normalized-pilot
& .\.venv\Scripts\python.exe scripts/bench_m2.py --repeats 3 --label acceptance
& .\.venv\Scripts\python.exe scripts/report_m2.py runtime/evidence/20261029T173111Z-m2-acceptance --development-runs runtime/evidence/20261029T172253Z-m2-pilot runtime/evidence/20261029T172447Z-m2-capacity-pilot runtime/evidence/20261029T172855Z-m2-normalized-pilot
& .\.venv\Scripts\python.exe scripts/m1.py stop
```

All **15 boundary tests passed** on the final inference source. They cover the M1 boundary plus M2 queue capacity/FIFO, per-identity outstanding limits, prompt bounds, strict proposal/state checks, deadline/circuit/no-retry behavior, response overflow/empty answers and an actual trickling HTTP stream. Compile checks passed. An additional exporter check refused an incomplete pilot as acceptance and retained pending human review. The export checks the entire expected 540-request matrix and all frozen thresholds. Git whitespace and documentation-link checks passed before handoff. Raw evidence and weights stay outside Git.
