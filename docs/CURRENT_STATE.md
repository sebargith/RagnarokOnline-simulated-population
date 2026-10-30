# Current state

Updated: 2026-10-30 (America/Santiago).

## Verified

- **Graphical startup configured and observed.** Local connection override,
  `Play-Local.cmd`, ordinary `roplayer` account and `Visitor` character are
  prepared. The actual client rendered the local-server selection screen.
  Credentials stay in ignored `runtime/player-client/PLAYER_ACCOUNT.txt`.
  User sign-in and graphical map entry remain pending; see the
  [client evidence](evidence/PLAYER-client-downloads.md). The continuous
  controller was started for this session; check live status before use.

- **Graphical client assets downloaded, not yet connected.** Matching dated
  EXEs, GRFs and supporting files are staged at
  `D:/Ragnarok Agents/runtime/player-client`. Archive/source hashes, PE32
  headers, direct DLL availability and Prontera map entries were checked.
  The initial download checks did not execute programs; graphical startup was
  subsequently observed as recorded above. [Download evidence](evidence/PLAYER-client-downloads.md).
  Successful graphical login/map entry remains unverified.

- **Coordinator review of Chat 06, 2026-10-30:** accepted the continuous
  fixture runtime for its demonstrated functional scope. All seven frozen
  evidence sets' raw hashes match; both final-source continuous manifests
  match the current implementation. Reviewed repeated cycles, addressed reply
  delivery during gameplay, stop/restart memory continuity and uncertain-trade
  recovery without replay. No additional gameplay or benchmark run was needed
  for this review. Graphical player access, current successful web search and
  long-duration stability are not established by these checks.

- **Chat 06: continuous M4 fixture runtime implemented**, branch
  `codex/m4-continuous`, worktree `D:/Ragnarok Agents/m4-continuous`, from
  reviewed `a523dbf`. Runtime commits `3cb8e39` and `575b1d8`; M2/M3 WIP stays
  in its original checkouts. One controller repeatedly runs solo/cooperative
  Poring hunts and loot, fixed affordable trade, Mira's patrol and bounded
  addressed dialogue. Start/stop/status/observe/manual public chat are in
  [README](../README.md#continuous-three-agent-runtime-m4-continuation-chat-06).
  Observation/interaction are headless; no graphical player client/assets or
  separate human account were supplied or verified.
- Final-source run `d3ac8c2d253c40538091ba020f360683` completed three
  hunt/loot cycles in **51.938 s**, delivered the selected 9B's reply while
  routine activity continued, and stopped with an unresolved transfer.
  Restart `590e0797b6a04495b28b2c72981b722b` reconciled it as **not_applied**
  from fresh client inventories and read-only server persistence, with
  **new_transfer_attempted: false**. It continued two cycles and Mira recalled
  the perceived public marker "ambercone" in a delivered reply. Identities
  and separately stored public-chat records survived; no memory was copied
  between identities. Both controllers stopped cleanly.
- **47 tests pass**, including 1,500 serial-window admissions without replay
  after eviction, 1,100 durable-journal actions, unknown-send protection,
  unaffordable-trade skip, stale-reply/target-readiness checks and byte-bounded
  rotation. Python compile and Perl syntax checks passed. The live event log
  actually rotated below its 1 MiB segment ceiling. The new live directory
  caps logs at four segments, with bounded status/results/queues and capped
  private memories; shared native-service logs remain outside this policy.
  [Continuous evidence](evidence/M4-continuous.md) records source/raw hashes,
  exact commands, outage/restart results and remaining limits.
- A development run with Ollama unavailable completed seven cycles and two
  confirmed trades while delivering fallback chat. The shell's old model-store
  path pointed to an empty store; the installed service was started with the
  existing user store `D:/Local_AI/Models/Ollama`, without a global setting
  change/download. The selected 9B digest matches its pin. The 30-second circuit
  cooldown permits new turns; it never retries the old prompt. No benchmark,
  social-quality review, one-hour stabilization or M5 was performed.
- Final-source legacy trade/observe modes also passed: Alden **16 Jellopy /
  170 Zeny -> 15 / 180**, Bram **7 / 30 -> 8 / 20**, independently checked
  after full login. The local SearXNG endpoint is currently unavailable:
  the Docker Linux backend was stopped and one startup attempt did not restore
  it. The web mode recorded `SearchUnavailable` and delivered its bounded
  fallback. No container
  was created/reconfigured; prior successful web evidence remains historical.

- **Coordinator review, 2026-10-30:** the controlled M4 functional prototype
  is accepted for its demonstrated scope. All five exported run summaries
  match raw evidence (excluding the documented resource-array projection),
  their raw file hashes match, and the final-repeat source manifest matches
  the current implementation. Interrupted recovery confirms a completed
  transfer with no new transfer attempted. No gameplay or benchmark rerun was
  needed for this read-only review. This does not establish continuous operation.

- **M4 functional prototype demonstrated**, clean branch `codex/m4-functional`
  at `D:/Ragnarok Agents/m4-worktree`, from exact handoff `42bddcc`.
  Three new project characters preserve M1 characters and all prior WIP.
  Runtime implementation commits: `a5bff27`, `f6b7a67`, `1c0b159`, `41f56d5`.
  Combined run `m4-20261030T114811Z` at `f6b7a67`
  recorded 353 events over about 71 seconds: three valid selected-9B replies,
  movement during pending inference, private-note isolation and perceived-chat
  learning with database reopen recall, solo 51 damage/loot, cooperative
  Alden 34 + Bram 17 damage to a fresh shared Poring/loot, and fixed trade.
  Alden Jellopy 3 -> 2 / Zeny 110 -> 120; Bram 1 -> 2 / 90 -> 80. Both fresh
  client inventories matched read-only server persistence after reconnect.
  Deliberate process exit `m4-20261030T115000Z` consumed zero completion
  observations; new-process recovery `m4-20261030T115034Z` confirmed exactly
  one transfer with **no new transfer attempted** (Alden 2/120 -> 1/130;
  Bram 2/80 -> 3/70). A separate local SearXNG check attributed a PC/pre-re
  source in 3.797 seconds. 40 tests, Python compile and Perl syntax passed.
  Sampled combined RAM floor **2.699 GiB**, GPU peak **9,827 MiB**; within-epoch
  snapshot gap <=1.031 seconds. Lifecycle subprocesses pause resource sampling;
  these are sampled values, not continuous peaks. No limits were changed.
  [M4 evidence](evidence/M4-prototype.md), [results/hashes](evidence/M4-results.json),
  [run/observe commands](../README.md#three-agent-functional-prototype-m4).
  This is a bounded controlled fixture, not an unattended population service.
  **Social-quality acceptance and one-hour stabilization remain deferred.**

- **M3 functional baseline complete; naturalness deferred by user direction.**
  On 2026-10-30 the user prioritized a working end-to-end prototype over dialogue
  polish. Committed baseline **ff635f5** on `codex/m3-persistent` is sufficient
  to begin the M4 functional prototype; social quality is **deferred, not passed**.
  Worktree: `D:\Ragnarok Agents\m3-worktree`; its three polish WIP files listed
  below are excluded from the handoff and must not enter the M4 starting state.
  Frozen code `beb18a7` ran **1800.657 s**, with **88 confirmed movement
  acknowledgments and seven peer-received chat replies**, one orchestrator
  restart and one map-server restart/reconnection. Both patrol cells were
  independently perceived by the peer. All 95 submitted actions were accepted
  and completed; no rejected/unknown results in this duration run. Identity,
  a spoken commitment and observed map were retrieved after restart; rumor
  and unknown-password probes did not invent knowledge. **36 tests passed**
  again after the run; **37 passed after the targeted search repair**.
  [Evidence](evidence/M3-persistence.md),
  [metrics/hashes](evidence/M3-results.json), [all replies](evidence/M3-conversations.md).
- M3 snapshot gaps were at most **1.033 s** before and **1.031 s** after the
  orchestrator restart; the forced map outage produced **25 disconnected
  snapshots**, then a new game epoch and resumed movement. Sampled RAM floor
  **6.235 GiB**, GPU peak **10,341 MiB** across 356 samples. No budget changed.
  An earlier attempt stopped before actions at 1.736 GiB RAM; the successful
  retry began after available RAM recovered to 7.727 GiB.
- M3 integrates bounded 9B dialogue, identity-scoped memory, movement-specific
  uncertainty reconciliation and one fixed public search topic. Short live
  inference/search outages preserved movement; stale/invalid output and
  uncertain restarts have automated checks. The final web query exported only
  a controller-owned literal and preserved its source, but selected a Ragnarok M
  snippet and gave an unhelpful refusal. Repair `7d875e5` now filters mobile
  sources, permits attributed external claims and retains complete generated
  sentences alongside explicit 80-character excerpts. A separate **35.406 s**
  live check selected a PC/pre-Renewal source, delivered a useful attributed
  summary and continued movement; its raw run is `m3-web-20261030T012548Z`.
  The 30-minute run predates this dialogue-only repair; controller/persistence
  sources are unchanged. Coordinator review found robotic phrasing and weak
  web-answer utility; these findings remain recorded. **Naturalness/social
  acceptance is deferred by the user, not passed. That M3 handoff did not implement M4.**

- **Preserved, uncommitted polish WIP:** `agent/dialogue.py`,
  `scripts/run_m3.py`, `tests/test_m3_dialogue.py`. Work stopped without further
  dialogue retests. These changes are unfinished and outside `ff635f5`; do not
  infer that the committed baseline's 37 passing tests verify this WIP. The
  three unrelated M2 repair files remain in the coordinator checkout as before.

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
- At the M1 handoff, all six game/database/bridge listeners were verified on `127.0.0.1`. A during-trial working-set sample across the six native processes totaled 635.62 MiB; it is not a peak or inference benchmark. Processes were stopped at that historical handoff; M3 leaves the server and test clients running.

## Boundaries and remaining limits

- M2's human review was deferred to the M3 live scenario by user direction. In the 9B sample dialogue, some replies imply a lent potion helped without a supplied use/result event, infer a connection timeout from a walk timeout, or assume the future meeting gate is the current location. These issues are visible in [samples](evidence/M2-conversations.md); passing structured recall does not complete conversational grounding or quality review.
- The fixed [M2 budget](../config/m2-limits.json) uses 2,048 context / 160 output tokens, thinking off, concurrency 1 / four queued / one outstanding per identity, service timeouts 20s warm / 60s first cold, overall deadlines 45s / 100s, no retry. Warm p95 targets are TTFT 1s, service 3s, queue 6s, response 8s; cold first TTFT <=15s and profile response <=20s. RAM floor 2 GiB available, total GPU ceiling 14 GiB. M3's three warm no-search samples had p95 TTFT **0.609 s**, service/response **0.891 s**, queue zero; two cold-budget turns had maximum TTFT **9.812 s** and response **10.344 s**. One web-assisted turn took **2.890 s** overall, separately measured. These few live turns are not a repeated M2 capacity benchmark. Long contexts and lifelong memory remain unverified; M3 scenario resource guards abort on a budget violation.
- M1 exposes only adjacent walkable-cell movement and ordinary printable public chat. One in-flight action, deadlines, game epochs, 128 retained request IDs, bounded nonblocking buffers, per-client tokens and finite reconnect budgets are implemented. Sending a packet is only `accepted`; matching server acknowledgment/echo is `completed`; timeout/disconnect is `unknown`. No automatic action resend exists.
- Snapshot positions can be OpenKore estimates; movement acknowledgment is not proof of arrival. Independent peer perception verified both patrol cells. M3 durably preserves unknown intent; movement can resume with a new goal after quiet/stable destination observations, without marking the old request completed. Unknown chat is abandoned without replay. This does not implement trade/item reconciliation.
- Stock pre-Renewal Prontera and a 30-minute adjacent-cell routine were tested; exact episode, graphical assets, combat/global routing, accepted social quality and longer operation remain unverified. Unsupported modern server features disable themselves with warnings. Retry exhaustion, deliberately lost game acknowledgments and output-buffer saturation were not separately live fault-injected.
- The initial failed DB bootstrap directory is preserved at `runtime/mariadb/data-initialization-attempt-1`. Active data is `runtime/mariadb/data`; never reinitialize or remove it as a routine troubleshooting step.
- **Evaluar arquitectura de población IA** is the main coordinator and evaluator. M2 was pushed on `codex/m2-inference`; the web-search slice is on `codex/web-search`, based on that branch. Neither is merged into main. Three unfinished M2 repair files remain uncommitted and excluded from web-search commits. The [user guide](USER_GUIDE.txt) tracks stages and starter prompts.
- M1 game/database/bridge processes and both clients were running at the web-search handoff. Existing databases, credentials, model stores and the Ollama app were preserved.

## Next action

User: sign in at the graphical local-server screen with credentials in
`runtime/player-client/PLAYER_ACCOUNT.txt` and select `Visitor`; then verify
Prontera rendering and the nearby agents. `Play-Local.cmd` relaunches the client.
The continuous controller was started and its fresh status showed `solo_hunt`,
two cycles, no reported error. Use README's status/stop commands to manage it.
SearXNG's offline Docker backend remains a separate outstanding service issue.
Unresolved transfers must be reconciled,
never bypassed by deleting state. Naturalness and one-hour stabilization remain
deferred; full M4 acceptance stays open. All M2/M3 WIP remains in its original
checkout. Do not start M5.
