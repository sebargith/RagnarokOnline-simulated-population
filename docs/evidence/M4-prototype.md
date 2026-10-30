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

## Combined demonstration and restart proof

The combined run **m4-20261030T114811Z**, frozen at **f6b7a67**, reported
`functional_complete: true` with 353 retained events, over approximately 71
seconds (resource sample at 70.546 s; the old summary did not store duration).
Five invalid actions, a stale session and duplicate replay were rejected.
A unique private test note began only in Alden's reported-claim memory, then
Bram and Mira received it through server public chat. All three recalled it
after reopening their own databases; no peer store was supplied as context.
Three valid model replies gave the expected names and preferences. Mira's
movement acknowledgment occurred while inference was pending.

| Slice | Server-confirmed outcome |
| --- | --- |
| Solo | Alden 3 hits / 51 damage, death event, Jellopy 1 -> 2 |
| Cooperation | Fresh target `5bb48e06`; Alden 34 damage, Bram 17; death event, Alden Jellopy 2 -> 3 |
| Trade | Alden Jellopy 3 -> 2, Zeny 110 -> 120; Bram Jellopy 1 -> 2, Zeny 90 -> 80 |

Alden selected the target from his own perception and sent the goal/roles in
public chat; Bram's perception of that exact message was required before his
agreement and action. Each attacker independently required the target in its
own fresh monster list. The leader observed death and collected a newly
appearing Jellopy, excluding older ground items. This is explicit deterministic
cooperation, not a claim of model-generated strategy or social sophistication.

The final hardening adds a 600-second wall-time cap, fresh reconciliation
timestamps, an interrupted-process mode, complete inference-source manifests
and a separate web check. The combined encounter/control behavior is unchanged;
the new reconciliation path and web mode were separately exercised, and all
40 tests passed again. No broad model benchmark was rerun.

**m4-20261030T115000Z** deliberately exited with code 1 after both final trade
packets. It consumed **zero trade completion results** and left the durable
transfer unknown. New process **m4-20261030T115034Z** reconnected the clients,
matched both inventories to persisted server balances and recorded exactly
one completed transfer: Alden 2 Jellopy/120 Zeny -> 1/130; Bram 2/80 -> 3/70.
It submitted **no new transfer**. The unit regression separately verifies that
unknown state survives restart and blocks a new transfer before reconciliation,
including stale/partial client observations and a mismatch against server data.

**m4-20261030T115058Z** exercised the existing local SearXNG service. Only
`Ragnarok Online classic Poring monster` was exported; the selected PC/pre-re
[source](https://ratemyserver.net/index.php?page=mob_db&mob_id=1002) stayed an
external claim. The 9B reply took 3.797 seconds including search and was sent
with an explicit `Web (ratemyserver.net)` prefix. The retained generated text
and its 80-character delivery excerpt are distinct. No private memory or game
state entered the search worker's query.

[Compact results, all dialogue and hashes](M4-results.json) link the four main runs and final repeat
to their raw evidence and source manifests. The combined run had sampled RAM
floor **2.699 GiB** and GPU peak **9,827 MiB**, with maximum within-epoch snapshot
gap **1.031 seconds**. Three cold-budget model responses took 12.484, 12.532 and
13.031 seconds; first TTFT was 12.015 seconds. These are short live samples,
not a repeated capacity benchmark. Resources were sampled about every five
seconds during the controller loop; samples paused during client lifecycle
subprocesses (combined maximum sample gap 15.328 seconds). The `m1` working-set
field is zero because this runner supplied no process-ID set; total available
RAM and GPU usage are the resource guard evidence. Full social-quality review,
one-hour stabilization, arbitrary routing/combat/trade and M5 remain unverified.

Final repeat **m4-20261030T115414Z** exercised the journal capacity guard on
normal actions and corrected the observer's movement goal to alternate on
repeated demonstrations. Mira moved back to 152,180 while inference was
pending; all three valid replies completed (1.094 / 1.656 / 2.140 seconds of
model response time on an already-loaded runner). This run also reopened the
same identity databases in a new orchestrator process. It is included in the
compact export with its final gameplay source hashes.

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
failure path, not a social-quality pass. The later combined run delivered all
three valid persona replies. Naturalness remains deferred by user direction.

## Commands actually run

PowerShell, from the M4 worktree, using the shared pinned Python:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -v
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_m4.py --runtime 'D:/Ragnarok Agents/runtime' --start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode solo
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode cooperate
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode conversation
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode all
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade --trade-fault after_commit_exit
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode web
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/report_m4.py --runtime 'D:/Ragnarok Agents/runtime' --combined m4-20261030T114811Z --combined-commit f6b7a67 --interrupted m4-20261030T115000Z --recovery m4-20261030T115034Z --web m4-20261030T115058Z --repeat m4-20261030T115414Z --output docs/evidence/M4-results.json
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
