# M3 persistence foundation (incomplete milestone)

This first slice implements only an identity-scoped SQLite record store. It is
not yet connected to the bridge, inference, or search and creates no autonomous
player. M3 acceptance remains pending.

`agent/memory.py` stores immutable persona bindings and distinct observations,
reported claims, generated dialogue, action records, and commitments. Each write
commits immediately. Duplicate keys are ignored per identity. Retention is 512
ordinary records plus 16 commitments per identity. Retrieval is at most 16 records
(8 by default) and 2,400 serialized data characters. Commitments are retrieved
first. Record payloads are limited to 4,096 serialized characters.

Executed in the clean `m3-worktree` checkout using the existing Python 3.11 venv:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -p test_m3_memory.py -v
```

Both tests passed. They verify close/reopen continuity, persona mismatch
rejection, identity isolation, retained unknown action status, commitment
provenance, duplicate suppression and retention after 530 ordinary writes.
These checks do not establish actual server-action reconciliation, model
grounding, responsiveness, social quality or 30-minute continuity.

Next: connect a deterministic adjacent-cell controller, preserving uncertain
requests and per-game-epoch bridge capacity across orchestrator restarts. Then
add a bounded background dialogue worker and controller-owned public search
queries before building the live acceptance harness. No M4 work is authorized.

## Deterministic controller slice

`agent/routine.py` now connects durable intent/capacity tracking to the existing
M1 bridge. It saves a unique request ID before sending, never automatically
replays an uncertain request, retains accepted/completed/rejected/unknown as
distinct outcomes, and rejects stale snapshots. Unknown outcomes block further
routine actions in the same epoch; a new observed epoch records uncertainty
before resetting capacity. This conservative same-epoch stop needs explicit
reconciliation in the later orchestration slice. Capacity is 110 reserved
actions per game epoch, retained across Python restarts, below M1's 128-entry
cache. The routine only requests adjacent movement every 20 seconds.

The final full suite passed: **31 tests in 3.790 seconds**, including send
failure preserving unknown status and capacity after restart. Compileall and
`git diff --check` passed. The initial broader-suite stall was reproduced with a five-second faulthandler
watchdog: Windows Python `socket.socketpair()` blocked in `socket.py:294 accept`
inside the sandbox. Outside the sandbox all seven existing bridge tests passed,
then the full 30-test suite passed in 3.946 seconds. This preceded the added
send-failure regression; the final suite count is recorded at the next commit.

Live M1 bridge listeners were absent because both registered OpenKore clients
had exited. Only those project clients were restarted using `scripts/m1.py`;
the database/server were left running. An initial routine stopped after one
acknowledgment because OpenKore's path-origin `position` differed from its
acknowledged `destination`. The corrected controller uses destination for
adjacent target selection and relies on the plugin's current-state recheck.

Corrected live command, executed from this worktree:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m3.py --runtime 'D:/Ragnarok Agents/runtime' --seconds 45
```

Result: 45.094 seconds, 53 events, two accepted actions followed by matching
`0087` movement acknowledgments to (150,180) and (151,180), no pending action at
exit. Raw bounded output: `runtime/evidence/m3-routine/live.txt` in the original
workspace. This is a short movement proof, not the 30-minute M3 scenario or
independent arrival verification. No inference/search has entered this slice.

A subsequent 25.031-second Python restart run received 30 events and one
accepted/completed movement acknowledgment to (150,180). The persisted epoch
counter increased from 3 to 4 and direction continued from -1 to +1, without
replaying earlier requests. Raw output: `runtime/evidence/m3-routine/restart.txt`.
Both live runs ended with no pending action. The fake-bridge regression, rather
than this live run, covers a restart with an unresolved accepted action.
