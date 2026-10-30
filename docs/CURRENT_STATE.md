# Current state

Updated: 2026-10-29 (America/Santiago).

## Verified

- **M3 started; persistence foundation only.** Clean branch `codex/m3-persistent`
  in `D:\Ragnarok Agents\m3-worktree` excludes the three unfinished M2 files.
  Memory and deterministic M1 movement controller are implemented. The full
  36-test suite passes outside the sandbox (socketpair stalls inside it).
  Corrected 45-second movement run passed with two server acknowledgments.
  Bounded 9B dialogue, one fixed public search topic, source separation and
  same-epoch movement reconciliation are implemented. Short live inference
  and search outage checks preserve routine movement.
  [Evidence and development grounding failures](evidence/M3-persistence.md).
  The frozen-source 30-minute run/reconnect and human review remain pending.

- **User direction changed on 2026-10-29:** stop model evaluation and use Qwen3.5 9B Q6_K for implementation. Original and failed grounding retests remain evidence, not quality acceptance. M3 must still review naturalness and unsupported claims. [M2 repair record](evidence/M2-inference.md).
- **Local web search slice works:** `scripts/ask_9b.py` completed a live 9B tool-call turn through the existing SearXNG JSON service on `127.0.0.1:8080`, with three source-linked snippets and no API key. The standalone turn has no bridge, persistence or gameplay action. [Configuration](../config/web-search.json) and [entry point](../README.md#local-9b-web-search-slice).
- The first revised final matrix (`233e49b`) passed frozen numeric checks for both models, but **failed broader grounding inspection**: [retained replies](evidence/M2-retest-conversations.md) include an invented safe place "Aden", unsupported reconnection, and unobserved recovery/checking claims. Further repair was stopped by user direction.
- **Original M2 measurement remains available; dialogue quality was not accepted.** [Evidence](evidence/M2-inference.md), [numeric results and source hashes](evidence/M2-results.json), [conversation review set](evidence/M2-conversations.md). Final run `20261029T173111Z-m2-acceptance` used frozen source/limits `be52a30`: **540 measured requests**, two installed models, runner-cold/warm profiles of 1/3/5 isolated sessions, three seeds/repetitions, five fixture requests per identity. No download, third candidate, global runtime change or M3 implementation.
- **User-selected model: Qwen3.5 9B Q6_K**, pinned in [operating configuration](../config/m2-operating.json), Windows Ollama 0.40.12. It passed all 162 structured checks and every frozen latency/resource target. Warm response p95 for 1/3/5 sessions: **1.657 / 4.844 / 6.360s**; cold-profile maximum response **12.860s**. Zero transport failures or truncations for 9B. The smaller 4B Q4_K_M baseline was faster but passed only 28/54 exact recall and 10/54 valid-move cases, with eight truncated conversation replies; it is not selected.
- M2 ran beside all six M1 server/database/client processes. Sampled GPU peak **9,952 MiB**; minimum available physical RAM **5.19 GiB**; peak system RAM used **26.66 GiB**; summed Ollama working-set peak **2.95 GiB** (private commit **11.80 GiB**, a different metric). Both clients supplied 660 connected snapshots each; maximum gaps **1.032 / 1.047s**, zero disconnected snapshots or monitor errors. This proves idle headless M1 coexistence and short inference profiles, not combat load, graphical-client capacity, or actual three/five autonomous players.
- M2 has reproducible conversation, scoped recall and simulated bounded-action fixtures, a one-worker/four-waiting FIFO, deadlines, finite streaming buffers and zero retries. No model proposal was executed in the game. All **15 boundary tests** and compile checks passed; source/raw hashes, token counts, variance, queue/TTFT/full latency and per-phase sampled resources are retained. Raw runs stay under ignored `runtime/evidence/*-m2-*`; the public review set is deterministic and includes every distinct failure/truncation pattern.
- **M1 passed.** [Actual results](evidence/M1-server-client-bridge.md), [tested hashes](evidence/M1-manifest.json), [commands](../README.md) and [bridge contract/troubleshooting](BRIDGE.md) carry the evidence and operating details. [M0](evidence/M0-environment.md) remains the historical environment audit.
- Native Windows rAthena `d4b8e7b8f16061cc2496d377ac8f777ce72a4f39`, pre-Renewal/protocol `20130807`, Release x64/v142/SDK 10.0.19041.0; portable MariaDB 10.11.19 x64; OpenKore `e0b04ee7090ff0bc9ab0fa6b876756c4b9004770` with Strawberry Perl 5.32.1.1 x86 and built matching XSTools; Python 3.11.9 x64. Both binary archives matched publisher SHA-256 values. The project path with spaces works without an alias.
- Duration run `20261029T162200Z` passed **600.031 s** continuously connected, ten movement round trips, maximum snapshot gap **1.033 s**, bidirectional chat, duplicate suppression, invalid/protocol rejection, and a real map-server shutdown/reconnect. The final reconnect/chat check took **14.093 s**.
- A final buffered-frame correction passed a targeted five-frame/cache-capacity regression. A subsequent complete restart and five-second live scenario passed on the final source (`20261029T163521Z`, 5.015 s, reconnect/chat 27.281 s). Seven Python boundary tests, compile checks and Perl syntax checks passed. The ten-minute run predates the framing correction; hashes distinguish them.
- Sources/portable tools/builds are in ignored `vendor/`; real credentials, SQL data, profiles, logs and raw traces in ignored `runtime/`; Python in `.venv/`. File-byte samples total about 2.57 GiB. Existing system tools and Ollama/models were preserved. M1 used no WSL/Docker, service/global PATH change, or new model.
- All six game/database/bridge listeners were verified on `127.0.0.1`. A during-trial working-set sample across the six native processes totaled 635.62 MiB; it is not a peak or inference benchmark. Project test processes are stopped at handoff.

## Boundaries and remaining limits

- M2's human review was deferred to the M3 live scenario by user direction. In the 9B sample dialogue, some replies imply a lent potion helped without a supplied use/result event, infer a connection timeout from a walk timeout, or assume the future meeting gate is the current location. These issues are visible in [samples](evidence/M2-conversations.md); passing structured recall does not complete conversational grounding or quality review.
- The fixed [M2 budget](../config/m2-limits.json) uses 2,048 context / 160 output tokens, thinking off, concurrency 1 / four queued / one outstanding per identity, service timeouts 20s warm / 60s first cold, overall deadlines 45s / 100s, no retry. Warm p95 targets are TTFT 1s, service 3s, queue 6s, response 8s; cold first TTFT <=15s and profile response <=20s. RAM floor 2 GiB available, total GPU ceiling 14 GiB. Only short English fixtures were measured (9B prompt maximum 289 tokens); long contexts, durable recall, live action freshness and responsive gameplay fallback remain unverified M3 work. Resource guards stop new admissions; a previously admitted burst can finish.
- M1 exposes only adjacent walkable-cell movement and ordinary printable public chat. One in-flight action, deadlines, game epochs, 128 retained request IDs, bounded nonblocking buffers, per-client tokens and finite reconnect budgets are implemented. Sending a packet is only `accepted`; matching server acknowledgment/echo is `completed`; timeout/disconnect is `unknown`. No automatic action resend exists.
- Snapshot positions can be OpenKore estimates; movement acknowledgment is not proof of arrival. Independent peer perception verifies this scenario. Durable reconciliation of uncertain actions remains M3 work.
- Stock pre-Renewal Prontera was tested; exact episode, graphical assets, combat/global routing, social behavior and long-duration operation are unverified. Unsupported modern server features disable themselves with warnings. Retry exhaustion, deliberately lost acknowledgments and output-buffer saturation were not separately fault-injected.
- The initial failed DB bootstrap directory is preserved at `runtime/mariadb/data-initialization-attempt-1`. Active data is `runtime/mariadb/data`; never reinitialize or remove it as a routine troubleshooting step.
- **Evaluar arquitectura de población IA** is the main coordinator and evaluator. M2 was pushed on `codex/m2-inference`; the web-search slice is on `codex/web-search`, based on that branch. Neither is merged into main. Three unfinished M2 repair files remain uncommitted and excluded from web-search commits. The [user guide](USER_GUIDE.txt) tracks stages and starter prompts.
- M1 game/database/bridge processes and both clients were running at the web-search handoff. Existing databases, credentials, model stores and the Ollama app were preserved.

## Next action

Continue M3 on `codex/m3-persistent` in `D:\Ragnarok Agents\m3-worktree`.
Run the frozen-source 30-minute scenario with orchestrator restart and map
reconnection; retain exact dialogue, timing/resource evidence and grounding
limits for human review before M4.
