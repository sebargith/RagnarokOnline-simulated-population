# Directing the Ragnarok Agents project

Updated: 2026-10-29 (America/Santiago). This is the user-facing map of what to ask Codex to do next. [ROADMAP](ROADMAP.md) defines acceptance, [CURRENT_STATE](CURRENT_STATE.md) records verified handoff facts, [ARCHITECTURE](ARCHITECTURE.md) records design boundaries, and [README](../README.md) has operating commands. Update this guide when milestone status, chat structure, or the intended experience changes; do not copy every technical finding into it.

## Goal and progress

Build believable, persistent AI players on a classic/pre-Renewal Ragnarok Online private server. Prove one grounded agent before a three-agent community. The first community experience should include **cooperative PvE and simple trade**. Five agents are a later capacity check, conditional on quality and resources.

| Stage | Status | What the status means |
| --- | --- | --- |
| M0 — Environment and deployment choice | **Done** | Native Windows layout selected; audit and version candidates recorded. |
| M1 — Server/client bridge | **Done, with a stated limit** | rAthena/OpenKore/Python connection, 600-second trial, movement, chat and reconnect passed. The final framing fix had a targeted regression and five-second live run, not a second 600-second trial. This is a control proof, not an autonomous agent. |
| M2 — Local inference benchmark | **Next; not started** | Compare two justified local candidates, including a smaller baseline; set the operating budget and obtain human review of sample conversations. |
| M3 — One persistent agent | **Waiting for M2** | Identity, grounded conversation, routine gameplay and memory across restart, with failure handling and human review. |
| M4 — Three-agent community | **Waiting for M3** | Isolated identities and relationships, cooperative PvE, simple trade and a one-hour reviewed trial. |
| M5 — Five-agent scale check | **Conditional on M4** | Expand only if three-agent quality and the measured resource budget support it. |

Do not mark a stage done because code exists or a model produced a plausible story. Use the [roadmap criteria](ROADMAP.md), actual test results and human review where specified. M0/M1 evidence is under [docs/evidence](evidence/); raw logs, credentials and game data stay outside Git.

## Which chat to use

**The existing planning and review chat is the main coordinator and evaluator.** Ask it to review milestone evidence, decide whether acceptance is met, record any change in direction, and integrate accepted work into GitHub `main`. It should not silently start the next milestone merely because the previous one passed.

Use **one focused implementation chat per milestone outcome** in the existing `D:\Ragnarok Agents` local project. Name the next one **03 - Local inference benchmark**. Later create **04 - One persistent agent**, **05 - Three-agent community**, and, only if warranted, **06 - Five-agent scale check**. Continue debugging the same outcome in its chat; do not create a chat for every file or test. Avoid simultaneous writers in the same checkout. If parallel work becomes useful, assign separate worktrees and coordinate shared ports, database state and GPU use.

Before implementation, have the chat inspect Git status, `AGENTS.md`, `CURRENT_STATE`, and the relevant roadmap section. It may consult other files as needed. Work on a `codex/` branch for a new milestone. Make **small, descriptive commits after verified steps**—for example, a benchmark harness, reproducible measurements, then a selection decision—rather than one large end-of-milestone commit or a commit after every prompt. Push the branch regularly under the standing authorization. The coordinator reviews the diff and evidence, then integrates accepted work into `main` without rewriting shared history. Do not commit secrets, model weights, databases or raw logs.

At each handoff, the implementation chat should provide the branch/commit range, what changed, checks actually run, evidence paths, failures or limitations, and one proposed next action. Update `CURRENT_STATE` at meaningful handoffs and this guide when statuses or directions change. Bring sample conversations to this coordinator chat for the human quality review; Codex's own rating is not a substitute.

## Prompt for chat 03 — Local inference benchmark

Create this chat now in the existing local project and paste:

```text
Implement M2 only, following AGENTS.md, docs/CURRENT_STATE.md and the
M2 criteria in docs/ROADMAP.md. Inspect Git status and the installed
Windows Ollama/model inventory, available RAM/VRAM and disk space first.
Reuse suitable assets. Compare two justified local candidates,
including a smaller baseline; add a third only for a recorded gap.

Build reproducible conversation, recall and bounded-action fixtures.
Measure cold/warm one-, three- and five-session profiles, ideally with
the M1 server/client load running. Record model artifacts and settings,
sample counts, token counts, response and queue latency, failures and
peak RAM/VRAM. Set explicit operating limits before final acceptance.
Prepare sample conversations for my review; do not mark human quality
review complete on your own.

Commit and push small reviewed steps, update docs/evidence/M2-inference.md
and docs/CURRENT_STATE.md, and hand the result to the coordinator chat.
Do not start M3 in this chat. If a model download or change in resource
budget is material, explain its size and reason before proceeding.
```

The coordinator should check reproducibility, resource fit beside M1, and sample quality. If no candidate meets the fixed budget, record the failure and a narrow adjustment instead of declaring a winner.

## Prompt for chat 04 — One persistent agent

Create only after M2's configuration and sample quality are accepted:

```text
Implement M3 only with the accepted M2 configuration and the proven
M1 bridge. Read AGENTS.md, docs/CURRENT_STATE.md and M3 in the roadmap.
Build one identity, deterministic routine gameplay, grounded dialogue,
bounded memory retrieval and a commitment that survives restart.
Keep observed events, beliefs, dialogue and confirmed actions distinct.
Validate every proposed action against fresh game state.

Run the 30-minute scenario and the specified inference failure, stale
proposal, invalid output and reconnect checks. Retain concise evidence
and conversation excerpts for my review. Commit and push small verified
steps, update CURRENT_STATE, and hand off to the coordinator. Do not
expand the population in this chat or mark human review complete yourself.
```

The coordinator accepts M3 only if continuity, grounding, fallback behavior, the M2 operating budget and human review all pass. A movement/chat routine does not establish combat or trade.

## Prompt for chat 05 — Three-agent community

Create only after M3 acceptance. Keep one chat for the outcome, with separate commits for the major verified slices:

```text
Implement M4 only, following AGENTS.md, CURRENT_STATE and the M4
roadmap criteria. First prove three isolated persistent identities and
controlled conversation. Then extend the restricted bridge and
deterministic controllers for a solo PvE fixture, cooperative PvE with
two agents, and a simple trade between project agents. Recheck game
state before actions; reconcile unknown transfers before retrying.

Run the one-hour three-agent scenario, knowledge-isolation test,
reconnect and resource checks. Record game-confirmed combat, loot and
both sides of the trade; prepare bounded social excerpts for my review.
Commit and push each verified slice, then hand off to the coordinator.
Do not claim cooperation from coincidental proximity or start M5.
```

The coordinator checks both believable social behavior and real game outcomes. If a bridge action is unsafe or unsupported, revise that small interface and its tests before claiming M4.

## Prompt for chat 06 — Five-agent scale check

Create only if M4 passes and measured headroom supports five agents:

```text
Implement M5 only. Reuse the accepted three-agent design and fixed
quality/resource targets. Add two distinct agents, repeat isolation,
persistence, cooperative PvE, trade, reconnect and social review with
five agents, and record the load and limits. Commit and push verified
steps. If the targets fail, keep the proven three-agent community and
report the limit instead of silently weakening the targets.
```

## Short prompt for a coordinator review

After a milestone chat hands off, ask here:

```text
Review the current milestone against its ROADMAP acceptance criteria.
Inspect the branch diff, CURRENT_STATE and retained evidence. Separate
verified outcomes from claims and untested limits; run proportional
checks. Tell me whether the milestone is accepted, what needs repair or
human review, and the exact next action. Update the guide/status and
integrate accepted commits into GitHub main when appropriate. Do not
start the next milestone unless I request it.
```
