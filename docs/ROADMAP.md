# Roadmap

Work on one milestone outcome at a time. Default order: M0 -> M1 -> M2 -> M3 -> M4. M1 and M2 can be investigated independently after M0, but sequential work is the default for this single-machine setup. Evaluation begins with the first experiment.

For each milestone, record starting state, commands and versions, observable outcomes, relevant failures, and evidence. Use `docs/evidence/M<number>-<topic>.md` when actual findings exist; keep large raw traces outside Git. Performance targets chosen after a baseline must be fixed before the final acceptance run. A failed target calls for a recorded decision, not silent relaxation.

## M0 - Environment audit and setup decision

Scope: inspect the repository, relevant installed tools, Windows/WSL, GPU/VRAM, storage, Git state, and any existing server/client/model assets the user identifies. Limit research to choosing a workable initial layout.

Done when:

- Verified facts are distinguished from user reports and unavailable checks.
- One recommended environment layout and candidate component/version combination are documented, including the client/protocol compatibility check still required in M1.
- Missing dependencies, expected downloads, locations, and consequential choices are explicit.
- The M1 implementation plan is small enough to review, with commands or a precise setup procedure. The user selects it by starting M1 with that plan.

Do not install dependencies, download models, or implement application code during this audit. Documentation and inspection scripts are permitted where useful.

## M1 - Server/client connection and control proof

Scope: prepare the selected local server and one agent-controlled client; prove a minimal Python-to-client control boundary before designing the full social system.

Done when:

- Reproducible setup, start, stop, and troubleshooting instructions include versions, shell, paths, and configuration templates without secrets.
- One client logs in, stays connected for a 10-minute trial, performs an observed movement/routine, and sends and receives a test chat message.
- Python receives normalized observations and requests at least one permitted action through the bridge; action success is tied to observed confirmation.
- A forced disconnect/reconnect and an invalid or failed command produce explicit outcomes without uncontrolled retries or duplicate side effects.

An integration failure is a useful result but does not complete M1. Record it and recommend the smallest change needed. Do not build a custom general-purpose client as an unplanned workaround.

## M2 - Local inference baseline and operating budget

Scope: benchmark two candidates initially, including a smaller baseline. Add a third only if a specific unresolved tradeoff warrants it. Reuse suitable installed assets where possible.

Done when:

- A reproducible harness records model identifier, artifact/quantization, runtime revision, context settings, generation limits, sampling settings, prompt fixtures, and hardware/runtime conditions.
- The same short conversation, recall, and bounded-action scenarios run repeatedly with isolated one-, three-, and five-agent request profiles. Record sample counts and variance; distinguish cold and warm runs.
- Results cover input/output tokens, time to first token, full response and queue latency, peak RAM/VRAM, failures, and human review of conversational behavior. Report development usage separately if available.
- One model/configuration is selected with explicit context, output, concurrency, timeout, queue, and latency targets. If none is viable, record a concrete reduction in requirements or another candidate instead of declaring a winner.

Benchmark against the resource budget needed by M1, ideally with the server/client running. Three/five request profiles test inference capacity; they do not establish that three/five game agents exist.

## M3 - One persistent, grounded agent

Scope: combine the proven bridge and inference configuration with one identity, a simple gameplay routine, bounded memory retrieval, and restart continuity.

Done when:

- A repeatable 30-minute scenario includes gameplay, conversation, one recorded commitment, and an orchestrator restart. The agent retains its identity and retrieves specified observed facts after restart.
- The agent can distinguish a rumor from an observed fact, lacks knowledge it was never given, and does not record a failed action as completed.
- Inference outage/timeout, stale proposals, invalid model output, and client reconnection have observable fallback behavior. Routine gameplay continues when inference alone fails.
- Critical state/action boundaries have automated checks; the end-to-end scenario has retained evidence and human review for continuity and naturalness.
- Measured latency and resource use meet the operating budget from M2, or the milestone remains explicitly incomplete pending an agreed adjustment.

## M4 - Three to five persistent agents

Start only after M3 passes. Introduce distinct preferences and schedules, agent-scoped relationships, and interactions over a one-hour trial, followed by longer runs as evidence warrants.

Done when three agents pass isolation, persistence, load, conversation-turn, and reconnect scenarios without runaway chat or unbounded memory/queues. Then repeat with five if the resource budget permits. Include a test in which only one agent learns a fact; other agents may learn it only through a recorded information path. Use human review and behavior metrics together before scaling further.
