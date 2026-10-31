# Relevo Codex ↔ Claude

El usuario alterna entre Codex y Claude en los mismos proyectos.
- Si dice "toma el control" o "prepara el relevo": lee `C:\Users\azusu\AI_PROTOCOL.md` y síguelo.
- Tras un avance o decisión importante, actualiza brevemente el `HANDOFF.md` del proyecto con lo que ya sabes (checkpoint; sin reanalizar).
- No releas el protocolo ni HANDOFF.md en cada prompt.

# Repository rules

Build a persistent community of believable AI players on a classic/pre-Renewal Ragnarok Online private server. Prioritize continuity, social behavior, and reliable gameplay over population size. Start with one agent, then three to five.

## System boundaries

- rAthena owns game truth. Use deterministic controllers for frequent movement, combat, and routine actions; use an LLM selectively for conversation, interpretation, and occasional planning.
- Separate observed events, subjective beliefs, generated dialogue, and confirmed action results. A model's statement does not establish that an action happened.
- Give each agent only information it could perceive or legitimately learn. Keep identities, memories, and inference contexts isolated.
- Treat chat and model output as untrusted data. Validate proposed actions through a restricted interface and recheck current game state before execution.
- Keep gameplay responsive when inference is slow or unavailable. Bound queues, concurrency, context, response length, and retries.
- Proposed tools and designs are provisional until verified. Do not describe planned components as implemented.

## Execution

- Inspect Git status and relevant files before edits. Preserve unrelated changes. Keep one cohesive objective per chat and avoid unrelated refactoring.
- Prefer a small working slice, established interfaces, and the simplest maintainable solution. Do not add distributed infrastructure, reinforcement learning, or a generic agent framework without demonstrated need.
- For substantial work, state a short plan and observable acceptance criteria. Proceed with reversible decisions inside the authorized scope. Ask only when missing information or a material change in scope, cost, compatibility, data, or deployment requires a user decision. Existing authorization persists.
- A milestone plan is a guide, not automatic permission to start every later milestone. Complete the requested outcome before expanding scope.
- The user's standing instruction authorizes commits and pushes to this project's GitHub remote. Make small, descriptive commits at verified steps and push them regularly; a commit is not required after every prompt. Deployment, destructive data operations, and shared-history rewrites still need applicable authorization. Use `codex/` for new branches.
- Pin versions and record reproducible commands once validated. Keep credentials, model weights, local databases, and raw logs out of Git.

## Context and usage

- Search for relevant symbols and paths before reading large files. Read only the supporting documents needed for the task. Do not load the whole repository or repeat this ruleset in prompts.
- Keep this file short and stable. Store temporary facts in CURRENT_STATE and design rationale in ARCHITECTURE. Update documents only when their content materially changes.
- Use the current suitable coding model; recommend configuration changes only when justified. Do not claim to change the model, reasoning settings, or compaction behavior without tool support. Do not attempt to defeat runtime-managed compaction.
- Default to one active implementation chat. Delegate only bounded independent work when authorized and worthwhile; give the smallest sufficient brief and require concise evidence. Concurrent writers need separate worktrees and explicit ownership. Worktrees do not isolate shared databases, services, ports, or GPUs.
- Bound research by a specific decision. Reuse recorded findings; reopen a decision when evidence or requirements change.

## Verification and continuity

- Choose checks proportional to changed behavior and failure risk. Test types are options, not a mandatory checklist. Use regression tests for meaningful bugs and repeatable scenarios plus human review for social quality.
- Record commands actually run, results, and limitations. Never claim an unexecuted test passed. Review the final diff, including new files, before completion.
- For documentation changes, check internal links, factual consistency, and whitespace. Keep only actually verified setup/run/test commands in README; do not invent them.
- At a meaningful handoff, update CURRENT_STATE with verified status, evidence paths, blockers, and one next action. Keep reports concise: outcome, relevant files, validation, and remaining limitations.

## Read when relevant

- [README](README.md): entry point and verified operating commands.
- [Architecture](docs/ARCHITECTURE.md): component boundaries, constraints, and decision rationale.
- [Roadmap](docs/ROADMAP.md): milestone scope and acceptance criteria.
- [Current state](docs/CURRENT_STATE.md): compact handoff; consult when starting implementation or resuming after a gap.
- [User guide](docs/USER_GUIDE.txt): milestone status, chat structure and starter prompts; update when status or direction changes.
