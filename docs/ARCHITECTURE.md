# Architecture and constraints

Status: initial design direction, not an implemented system. Validate the integration and resource assumptions before building the social layer. Milestone criteria belong in [ROADMAP](ROADMAP.md); observed progress belongs in [CURRENT_STATE](CURRENT_STATE.md).

## Components and ownership

| Component | Initial direction | Responsibility |
| --- | --- | --- |
| Game server | rAthena, pre-Renewal | Authoritative world state, action outcomes, game rules |
| Game persistence | MySQL/MariaDB | rAthena's supported game database |
| Client/controller | OpenKore candidate | Login, perception, deterministic gameplay; prove external control first |
| Orchestrator | One Python process initially | Agent scheduling, event normalization, action validation, inference queue |
| Agent persistence | SQLite initially | Identities, observations, beliefs, relationships, commitments; separate from game DB |
| Language inference | Shared local runtime; llama.cpp candidate | Bounded requests with isolated per-agent context |

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

## Contracts to establish in M1 and M3

- Normalize events with agent identity, source, time, and an identifier suitable for duplicate detection. Preserve the source of memories and distinguish observation, reported claim, and inference.
- Identify action requests and results. Distinguish accepted, completed, failed, and unknown outcomes. After disconnects or timeouts, reconcile state before retrying actions that could duplicate a trade, message, or item use.
- Scope perception by agent. A global administrator view may help debugging but must not silently enter an agent's knowledge.
- Validate model proposals against an allowed command schema and current state. Player messages cannot change system instructions or grant administrative access.
- Store raw observations separately from summaries where needed for diagnosis. Bound retrieval and retention; do not append an entire lifetime of chat to each request. Begin with simple structured retrieval before considering embeddings.
- Define finite inference budgets, stale-request handling, and a fallback. Gameplay continues through inference outages; conversation may wait or be skipped without fabricated claims.

## Hardware and environment

M0 verified Lenovo model 82N6, Ryzen 9 5900HX (8 cores/16 threads), RTX 3080 Laptop with 16 GiB VRAM, 31.86 GiB visible system RAM, Windows 11, and WSL2 Ubuntu 22.04.4. The user-reported Legion marketing model was not independently resolved. Resource snapshots and installed versions are in [M0 evidence](evidence/M0-environment.md).

Use this machine initially without buying hardware or relying on paid inference. M0 recommends one WSL gameplay environment: rAthena, MariaDB, OpenKore, and Python, with external sources/builds/runtime data on Ubuntu's Linux filesystem and this repository remaining on D:. Existing Windows Ollama is an M2 reuse candidate; its WSL connection and performance remain untested. The recommendation awaits acceptance through M1 and is not an installed deployment. Record the shell and filesystem boundary; do not maintain two competing gameplay environments by default.

## Provisional decisions and alternatives

- Try OpenKore first to reuse gameplay functionality. Validate the rAthena/client protocol and a minimal Python bridge before committing to it. If unsuitable, compare one concrete alternative against the failing requirement.
- Benchmark a small shortlist of local models against realistic prompts. Qwen-family and 27B-class candidates may be considered, but neither family nor size is a requirement. Include a smaller viable baseline.
- A model loading successfully is insufficient evidence. Measure prompt processing, end-to-end latency, queueing, memory, and quality under one, three, and five logical sessions. Shared weights do not eliminate context-memory costs.
- Add only minimal identity and memory to the first conversational slice. Expand relationships and goals after restart continuity works.
- Choose the initial conversation language and pre-Renewal content/ruleset during setup. Use a documented provisional default if the choice is reversible; do not silently mix datasets or client versions.

## References

- [rAthena requirements](https://github.com/rathena/rathena/blob/master/README.md): includes MySQL/MariaDB.
- [OpenKore source](https://github.com/OpenKore/openkore): inspect the pinned revision when validating integration.
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md): runtime options, slots, cache controls, and metrics.

Upstream links are discovery sources. Record the revisions actually tested in milestone evidence.
