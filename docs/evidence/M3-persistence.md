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
