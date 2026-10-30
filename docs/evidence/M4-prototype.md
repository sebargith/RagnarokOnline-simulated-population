# M4 functional prototype evidence

Started 2026-10-30 from `42bddcc` (M3 runtime `ff635f5`), clean worktree
`D:/Ragnarok Agents/m4-worktree`, branch `codex/m4-functional`.
The coordinator's M2 WIP and the M3 dialogue WIP were preserved.

## Verified slices

- `a5bff27`: three private SQLite stores and personas, one shared bounded 9B
  scheduler, addressed turns only; 38 tests passed.
- Solo run `runtime/evidence/m4-20261030T113817Z`: three server attacks, 51
  damage, server monster death and Jellopy inventory 0 -> 1. This development
  run exposed repeated adjacent goals before a new snapshot; navigation was
  corrected to wait for fresh perception and avoid occupied player cells.
- Cooperative development run `m4-20261030T113927Z`: Alden proposed the shared
  target/roles in public chat, Bram agreed, both caused 17 damage to that target,
  server death, Alden Jellopy 1 -> 2. This target had damage from a preceding
  aborted navigation attempt; a fresh combined run is still required.
- Trade run `m4-20261030T114632Z`: both participants received server engagement,
  offer/lock and completion evidence. After both clients logged in again,
  inventories matched read-only rAthena persistence: Alden Jellopy 2 -> 1,
  Zeny 100 -> 110; Bram Jellopy 0 -> 1, Zeny 100 -> 90.
- 40 tests and Perl syntax check passed after the trade/readiness repairs.

The three NEW test characters are M4 Alden, M4 Bram and M4 Mira (ordinary
novices, accounts 2000010..2000012). They have normal Basic Skill level 1 for
trade. No M1 character, database initialization or model asset was replaced.
The local fixture adds one stationary Poring at Prontera 154,180, retaining
normal combat/drops, with a guaranteed server-created Jellopy reward and a
15-second respawn. This is a controlled fixture, not global autonomous PvE.

## Repairs and uncertainty

The first trade request lacked the normal novice skill prerequisite. A second
attempt exposed the legacy Zeny acknowledgment path. Neither was replayed:
each was reconciled against fresh inventories, with balances unchanged. The
first reconciliation initially saw an early empty client inventory and stayed
ambiguous until a subsequent read proved it not applied. OpenKore's legacy
`isReady()` is constant true; it cannot establish full-login inventory truth.
The verifier now requires fresh-login observations to match both persisted
server balances after graceful client disconnect. The read-only SQL verifier
is privileged test instrumentation and is never supplied to a player mind.
The buyer's fixed Zeny offer is locked in the same operation; both observed
offers and locks must match before either final commit. Unknown/ambiguous
transfers persist and block a new transfer; there is no automatic action retry.

An initial conversation run delivered two valid persona replies and one
validated fallback after invalid model output. This is retained as a functional
failure path, not a social-quality pass. The final combined demonstration,
lost-completion check and live boundary/isolation checks are still pending.

## Commands actually run

PowerShell, from the M4 worktree, using the shared pinned Python:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -v
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_m4.py --runtime 'D:/Ragnarok Agents/runtime' --start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode solo
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode cooperate
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode conversation
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade
```

Perl syntax was checked with the pinned Perl, sanitized `m1.env_perl()`, and
OpenKore `src` plus `src/deps` on `@INC`. A first bare invocation failed on DLL
loading and another without `src/deps` failed on Carp::Assert; neither was a
successful check. Socket tests and local-service commands need execution
outside the restricted network sandbox.

Raw event files, source hash manifests, summaries, character data and credentials
remain under ignored `runtime/`. Each run has a 12,000-event hard cap; player
memory and dialogue/inference budgets remain bounded. Richer social quality,
the one-hour stabilization trial and M5 are outside this functional proof.
