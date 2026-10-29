# Architecture and constraints

Status: M1's native server/client bridge passed its acceptance checks. The inference, persistence and social components below remain design direction. Milestone criteria belong in [ROADMAP](ROADMAP.md); observed progress belongs in [CURRENT_STATE](CURRENT_STATE.md).

## Components and ownership

| Component | Initial direction | Responsibility |
| --- | --- | --- |
| Game server | rAthena, pre-Renewal | Authoritative world state, action outcomes, game rules |
| Game persistence | MySQL/MariaDB | rAthena's supported game database |
| Client/controller | Pinned native OpenKore plus project plugin | M1 implements login, scoped perception, validated adjacent movement/public chat and bounded reconnect |
| Orchestrator | Python bridge client now; one orchestrator planned | M1 reads normalized events and submits requests; scheduling and inference queue remain later work |
| Agent persistence | SQLite initially | Identities, observations, beliefs, relationships, commitments; separate from game DB |
| Language inference | Shared native Windows runtime; existing Ollama reuse or llama.cpp candidate | Bounded requests with isolated per-agent context |

Prefer one orchestrator and a simple persistence owner initially. An agent is a logical identity, not necessarily a separate process or loaded model. Avoid services and frameworks that the first slice does not need.

```text
rAthena -> client observations -> agent-scoped events -> memory/beliefs
                                    |                       |
                           gameplay controller      context selection
                                    |                       |
                                    |                 shared LLM queue
                                    |                       |
                                    +---- action validation <- proposal
                                                |
                                         client command
                                                |
                                      confirmed game result
```

## Bridge contract and later persistence

[BRIDGE](BRIDGE.md) documents the implemented M1 schemas and limits. One nonblocking loopback TCP stream per client uses a runtime token, game epochs, bounded buffers, one in-flight action and retained request IDs. The plugin validates live game state immediately before sending a move/chat packet. Packet transmission yields `accepted`; matching server acknowledgment/echo yields `completed`; timeout/disconnect yields `unknown`. The live harness verifies movement and chat against a separate test peer. OpenKore snapshot coordinates can be interpolated; movement acknowledgment does not establish arrival.

M1 contains no LLM, durable agent memory or automatic retry of uncertain actions. The following persistence and inference responsibilities remain M3 work:

- Normalize events with agent identity, source, time, and an identifier suitable for duplicate detection. Preserve the source of memories and distinguish observation, reported claim, and inference.
- Identify action requests and results. Distinguish accepted, completed, failed, and unknown outcomes. After disconnects or timeouts, reconcile state before retrying actions that could duplicate a trade, message, or item use.
- Scope perception by agent. A global administrator view may help debugging but must not silently enter an agent's knowledge.
- Validate model proposals against an allowed command schema and current state. Player messages cannot change system instructions or grant administrative access.
- Store raw observations separately from summaries where needed for diagnosis. Bound retrieval and retention; do not append an entire lifetime of chat to each request. Begin with simple structured retrieval before considering embeddings.
- Define finite inference budgets, stale-request handling, and a fallback. Gameplay continues through inference outages; conversation may wait or be skipped without fabricated claims.

## Hardware and environment

M0 verified Lenovo model 82N6, Ryzen 9 5900HX (8 cores/16 threads), RTX 3080 Laptop with 16 GiB VRAM, 31.86 GiB visible system RAM, Windows 11, and WSL2 Ubuntu 22.04.4. The user-reported Legion marketing model was not independently resolved. Resource snapshots and installed versions are in [M0 evidence](evidence/M0-environment.md).

The user selected native Windows on 2026-10-29, with project-local files where practical. Run rAthena, MariaDB, OpenKore and Python as Windows processes from this project. Put external source/build trees and portable MariaDB/Perl in `vendor\`, mutable DB/configuration/logs in `runtime\`, and the Python environment in `.venv\`, all under `D:\Ragnarok Agents` and ignored by Git. Reuse existing system Git/Python/Visual Studio tools and Ollama/model assets in place. This keeps new project-owned files together without copying installed tools or large existing models. WSL findings remain historical audit evidence; WSL/Docker are outside the selected deployment.

Portable MariaDB 10.11.19 x64 runs as an explicitly started process. rAthena builds with the installed VS 2019/v142 tools and SDK 10.0.19041.0. Portable Strawberry Perl 5.32.1.1 loads the built 32-bit XSTools DLL; Python 3.11.9 x64 communicates across TCP. Build/launch and gameplay worked in the project path with spaces; no drive alias, service, global PATH change or additional system runtime installation was needed. Keep eight GiB free before initial setup; actual footprint/resource samples belong in milestone evidence. No hardware purchase or paid inference is used.

## Provisional decisions and alternatives

- Retain OpenKore for the first slice: the pinned protocol now supports login, decoded observations and restricted external control. Global routing/combat and long-run social behavior are not established by M1.
- Benchmark a small shortlist of local models against realistic prompts. Qwen-family and 27B-class candidates may be considered, but neither family nor size is a requirement. Include a smaller viable baseline.
- A model loading successfully is insufficient evidence. Measure prompt processing, end-to-end latency, queueing, memory, and quality under one, three, and five logical sessions. Shared weights do not eliminate context-memory costs.
- Add only minimal identity and memory to the first conversational slice. Expand relationships and goals after restart continuity works.
- Expand from one persistent agent to three only after continuity works. The first community demonstration includes cooperative PvE and simple trade; extend the restricted bridge and deterministic controllers in measured slices, confirming combat, loot and transfers from game observations before claiming success. Five agents are a later capacity check.
- M1 uses English test messages and stock pre-Renewal data/rates on Prontera. An exact historical episode and future conversation language remain choices before content/social customization.

## References

- [rAthena requirements](https://github.com/rathena/rathena/blob/master/README.md): includes MySQL/MariaDB.
- [OpenKore source](https://github.com/OpenKore/openkore): inspect the pinned revision when validating integration.
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md): runtime options, slots, cache controls, and metrics.

Upstream links are discovery sources. Record the revisions actually tested in milestone evidence.
