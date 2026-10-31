# Architecture and constraints

## Dirección aprobada — 2026-10-31

El [plan vigente](NATIVE_AGENT_PLAN.md) prioriza un personaje normal desde nivel 1.
OpenKore será el único ejecutor de navegación, combate y rutinas reactivas; Python
validará objetivos y resultados, conservará memoria y solicitará inferencia
selectiva al 9B. El modelo podrá consultar mecánicas públicas mediante SearXNG,
con presupuestos y fuentes, cuando esa capacidad se amplíe y verifique.

Esta integración está pendiente. Hoy las demos arrancan con `--ai=off` y Python
dirige acciones individuales. No activar dos controladores sobre el mismo
personaje ni exponer consola libre al LLM. El adaptador conservará percepción
aislada, sesiones, límites y la diferencia entre aceptación y resultado. Los
componentes descritos abajo corresponden a la base implementada de las demos;
sus fixtures y criterios no equivalen a progreso autónomo general.

## Base implementada

Status: M1 passed; M3's persistent functional baseline and M4's controlled
three-agent demonstration are recorded. M4 now also has a continuous fixture
controller with bounded request/evidence retention, asynchronous addressed
dialogue, repeated PvE/loot/trade and stop/restart recovery. Social-quality
acceptance and the one-hour M4 trial remain deferred. Milestone criteria belong in
[ROADMAP](ROADMAP.md); verified evidence belongs in [CURRENT_STATE](CURRENT_STATE.md).

## Components and ownership

| Component | Initial direction | Responsibility |
| --- | --- | --- |
| Game server | rAthena, pre-Renewal | Authoritative world state, action outcomes, game rules |
| Game persistence | MySQL/MariaDB | rAthena's supported game database |
| Client/controller | Pinned native OpenKore plus project plugin | Scoped perception, validated adjacent movement/public chat, controlled M4 combat/loot/trade and bounded reconnect |
| Orchestrator | One Python M4 process | Three fixture routines, durable intent, one background dialogue turn and pending reply per identity; shared OS ownership lock |
| Agent persistence | Identity-scoped SQLite records | Persona, observations, reported claims, dialogue, action outcomes and commitments; bounded retention/retrieval; separate from game DB |
| Language inference | Selected Qwen3.5 9B Q6_K on native Windows Ollama | Bounded M3 dialogue requests with identity-scoped context; no model gameplay authority |
| Public web search | Existing local SearXNG container, JSON API on loopback | One fixed public topic in M3; at most one search per turn; snippets are external claims with URLs, not game truth |

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

M1 itself contains no LLM or durable agent memory. M3 now owns durable records,
movement intent and bounded dialogue through `agent/` and `scripts/run_m3.py`.
The following persistence and inference constraints continue to apply:

- Normalize events with agent identity, source, time, and an identifier suitable for duplicate detection. Preserve the source of memories and distinguish observation, reported claim, and inference.
- Identify action requests and results. Distinguish accepted, completed, failed, and unknown outcomes. After disconnects or timeouts, reconcile state before retrying actions that could duplicate a trade, message, or item use.
- Scope perception by agent. A global administrator view may help debugging but must not silently enter an agent's knowledge.
- Validate model proposals against an allowed command schema and current state. Player messages cannot change system instructions or grant administrative access.
- Store raw observations separately from summaries where needed for diagnosis. Bound retrieval and retention; do not append an entire lifetime of chat to each request. Begin with simple structured retrieval before considering embeddings.
- Define finite inference budgets, stale-request handling, and a fallback. Gameplay continues through inference outages; conversation may wait or be skipped without fabricated claims.
- Integrate the standalone web-search turn through identity-scoped context. Never place private memory or observed game state in a query; keep web results source-labeled, short and untrusted. Search failure must not block the deterministic gameplay controller.

The M4 continuation runs one persistent fixture controller in
`agent/continuous.py`, reusing the reviewed deterministic navigation, combat,
loot and fixed-trade primitives. Routine waits pump all three perceptions and
bounded dialogue delivery; Mira's adjacent patrol runs in that pump. The model
has no gameplay authority. A bounded local command/status interface lets a
headless user interact without a second consumer on the bridge sockets.

Continuous operation uses per-client monotonic request IDs plus a retained
high-water mark rather than evicting arbitrary duplicate IDs. This removes the
128-request lifetime stop without making evicted requests executable. Durable
uncertain transfers remain separate from the rolling terminal action history.
Logs rotate in a fixed shared live directory; starting a controller does not
create an accumulating sequence of evidence directories. Existing shared
native-service logging is preserved. The controller still uses a deliberately
limited Prontera fixture; long-duration and social acceptance remain open.

## Hardware and environment

M0 verified Lenovo model 82N6, Ryzen 9 5900HX (8 cores/16 threads), RTX 3080 Laptop with 16 GiB VRAM, 31.86 GiB visible system RAM, Windows 11, and WSL2 Ubuntu 22.04.4. The user-reported Legion marketing model was not independently resolved. Resource snapshots and installed versions are in [M0 evidence](evidence/M0-environment.md).

The user selected native Windows on 2026-10-29, with project-local files where practical. Run rAthena, MariaDB, OpenKore and Python as Windows processes from this project. Put external source/build trees and portable MariaDB/Perl in `vendor\`, mutable DB/configuration/logs in `runtime\`, and the Python environment in `.venv\`, all under `D:\Ragnarok Agents` and ignored by Git. Reuse existing system Git/Python/Visual Studio tools and Ollama/model assets in place. This keeps new project-owned files together without copying installed tools or large existing models. The game stack remains native. The existing local SearXNG instance uses Docker; its last known backend state is unavailable. Restoring it is a separate search task, not a migration of the game stack to WSL/Docker.

Portable MariaDB 10.11.19 x64 runs as an explicitly started process. rAthena builds with the installed VS 2019/v142 tools and SDK 10.0.19041.0. Portable Strawberry Perl 5.32.1.1 loads the built 32-bit XSTools DLL; Python 3.11.9 x64 communicates across TCP. Build/launch and gameplay worked in the project path with spaces; no drive alias, service, global PATH change or additional system runtime installation was needed. Keep eight GiB free before initial setup; actual footprint/resource samples belong in milestone evidence. No hardware purchase or paid inference is used.

## Provisional decisions and alternatives

- Retain OpenKore for the first slice: the pinned protocol now supports login, decoded observations and restricted external control. Global routing/combat and long-run social behavior are not established by M1.
- Use the user-selected Qwen3.5 9B Q6_K for M3. M2 measured latency, queueing, memory and short-prompt structured behavior under one, three and five logical sessions; failed grounding probes remain a live quality risk.
- Keep public web search in the Python tool boundary through the existing local SearXNG service. SearXNG forwards public queries to configured external engines. The M3 worker receives only a controller-owned public query literal, never player chat or memory. Web-answer inference receives one source snippet and no private records; the retained reply preserves its exact URL.
- Add only minimal identity and memory to the first conversational slice. Expand relationships and goals after restart continuity works.
- Expand from one persistent agent to three only after continuity works. The first community demonstration includes cooperative PvE and simple trade; extend the restricted bridge and deterministic controllers in measured slices, confirming combat, loot and transfers from game observations before claiming success. Five agents are a later capacity check.
- English is the selected dialogue target. M1 uses stock pre-Renewal data/rates on Prontera; an exact historical episode remains a choice before content customization.

## References

- [rAthena requirements](https://github.com/rathena/rathena/blob/master/README.md): includes MySQL/MariaDB.
- [OpenKore source](https://github.com/OpenKore/openkore): inspect the pinned revision when validating integration.
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md): runtime options, slots, cache controls, and metrics.

Upstream links are discovery sources. Record the revisions actually tested in milestone evidence.
