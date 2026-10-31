# Ragnarok Online AI Agents

A local-first project for persistent, socially believable AI players on a classic/pre-Renewal Ragnarok Online private server. The first target is one autonomous player with grounded conversation and memory across restarts, followed by three to five distinct players.

**Current direction (2026-10-31):** the user approved one normal level-1 player
with native OpenKore execution, followed by bounded 9B goals and web knowledge.
See the [approved plan](docs/NATIVE_AGENT_PLAN.md) and [Claude handoff](HANDOFF.md).
This is the next implementation, not a capability already delivered. The existing
M4 runtime is a controlled three-agent fixture; its [evidence](docs/evidence/M4-continuous.md)
remains valid for that scope. Social polish and the one-hour trial remain deferred.

## Start here

The project entry point is `D:\Ragnarok Agents`; current implementation continues
in the existing checkout `D:\Ragnarok Agents\m4-continuous`, branch
`codex/single-agent-plan`. Read the [user guide](docs/USER_GUIDE.txt) for the next
prompt, [current state](docs/CURRENT_STATE.md) for verified facts and
[bridge contract](docs/BRIDGE.md) for the implemented demo interface. Commands
below operate the existing demos; they do not launch the planned native agent.

- [General development rules](AGENTS.md)
- [Architecture and remaining design](docs/ARCHITECTURE.md)
- [Milestones and acceptance criteria](docs/ROADMAP.md)
- [Verified current state and next action](docs/CURRENT_STATE.md)
- [Project direction guide and starter prompts](docs/USER_GUIDE.txt)

## Setup and operation

Use PowerShell 7 at `D:\Ragnarok Agents`. Python 3.11.9, VS 2019 Build Tools/MSVC v142 and SDK 10.0.19041.0 are reused in place. [Version pins](config/versions.json) include the exact rAthena/OpenKore commits, portable archive SHA-256 values, protocol `20130807` and 144-byte character blocks.

One-time setup for a new workspace (initialization refuses existing database data):

```powershell
Set-Location 'D:\Ragnarok Agents'
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe scripts/m1.py acquire
& .\.venv\Scripts\python.exe scripts/m1.py build
& .\.venv\Scripts\python.exe scripts/m1.py configure
& .\.venv\Scripts\python.exe scripts/m1.py initialize
```

`acquire` checks 8 GiB free space, pins source revisions, verifies both binary ZIP hashes, and extracts portable tools under `vendor/`. Native compilation uses two build workers. `configure` restores the local test profiles and reuses generated credentials. Do not run initialization again on this prepared workspace.

Start/observe/stop the existing setup:

```powershell
& .\.venv\Scripts\python.exe scripts/m1.py start
& .\.venv\Scripts\python.exe scripts/m1.py client agent
& .\.venv\Scripts\python.exe scripts/m1.py client peer
& .\.venv\Scripts\python.exe scripts/observe.py agent --seconds 5
& .\.venv\Scripts\python.exe scripts/m1.py status
& .\.venv\Scripts\python.exe scripts/m1.py stop
```

The peer is a temporary headless test client for independent movement/chat observation. It can be omitted outside verification. All six listeners bind to `127.0.0.1`: database `3306`, login `6900`, character `6121`, map `5121`, agent bridge `8765`, peer bridge `8766`. No graphical client or game asset download is required for this proof.

Run unit checks, then the live acceptance harness with both clients started:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe scripts/accept_m1.py --seconds 600
```

The live check includes a ten-minute connection/routine, bidirectional chat, invalid/duplicate requests, protocol failures, and an actual map-server shutdown/restart. It writes bounded raw observations and actual results under `runtime/evidence/<UTC-run-id>/`. `--seconds 5` is a development smoke run and does not satisfy M1's duration requirement.

External sources/builds/portable tools are in `vendor/`; mutable databases, credentials, configuration, logs and evidence are in `runtime/`; Python is in `.venv/`. Keep these ignored directories out of Git. M1 leaves existing Ollama/model stores in place and uses no WSL/Docker or inference runtime.

See [BRIDGE](docs/BRIDGE.md) for schemas, confirmation limits, reconnect budgets and known setup fixes. The [M0 audit](docs/evidence/M0-environment.md) is historical environment evidence; M1 records actual implementation results separately.

## Local inference benchmark (M2)

Reuse installed Windows Ollama **0.40.12** and the two exact assets in [candidate pins](config/m2-candidates.json). The harness checks version/digests, requires no preloaded model and does not download assets or alter global Ollama settings. Start both M1 clients using the commands above, then run:

```powershell
& .\.venv\Scripts\python.exe scripts/bench_m2.py --repeats 3 --label acceptance
```

This runs 540 short fixture requests plus 18 warm-up requests and prints its ignored evidence directory. It sends no model action to the game. [M2 evidence](docs/evidence/M2-inference.md) records the pilot/final/export commands, exact operating limits, failure patterns and resource measurement limits. The [9B configuration](config/m2-operating.json) passed fixed technical targets, but later grounding probes found unsupported claims. The user selected 9B for implementation and deferred conversational quality review to M3.

## Local 9B web search slice

The existing self-hosted SearXNG container serves JSON search on `127.0.0.1:8080`. The model uses Ollama's local tool-call API; Python validates one search request, queries SearXNG, and returns at most three short, source-linked snippets. Search results are external claims and never establish game actions or rAthena state. This standalone command does not connect to the game; M3/M4 separately integrate a fixed public topic.

With SearXNG and Ollama running, this command was verified:

```powershell
& .\.venv\Scripts\python.exe scripts/ask_9b.py 'Search the web for the iRO Wiki Prontera page and tell me its URL.'
```

The endpoint and limits are in [web-search configuration](config/web-search.json). SearXNG needs no API key, but sends public queries to its configured internet search engines. If the local service is unavailable, the turn reports the failure. M3 separately integrates a fixed public query through a worker that receives no private context; its narrow relevance filter is not a general search-quality guarantee.

## Persistent agent scenario (M3)

The implementation worktree is `D:\Ragnarok Agents\m3-worktree`; shared native
services, Python and runtime data remain in `D:\Ragnarok Agents`. With both M1
clients, Ollama and SearXNG running, this exact command completed the recorded
30-minute trial from the implementation worktree:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/accept_m3.py --runtime 'D:/Ragnarok Agents/runtime' --seconds 1800 --reconnect
```

It schedules an orchestrator restart and a local map-server restart, and writes
ignored evidence under the shared runtime directory. It requires at least
2 GiB available RAM and no other orchestrator using that runtime. Test dialogue
uses the `M3:` prefix; only `M3: web poring` enables the fixed public search.
The patrol has no combat, loot, trade or global navigation.

[M3 evidence](docs/evidence/M3-persistence.md) records the exact tested commit,
outage checks, failed preflights, latency/resources and remaining acceptance
limits. [Results and hashes](docs/evidence/M3-results.json) accompany the
retained conversation review set.

## Native single-player navigation (P1a)

Separate normal novice, OpenKore `--ai=manual`, bridge port 8770. Requires the
local server/database already running; creates only new P1 records and does not
touch M1/M4 clients. [Evidence and limits](docs/evidence/P1a-native-navigation.md).

```powershell
Set-Location 'D:/Ragnarok Agents/m4-continuous'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_p1.py prepare --runtime 'D:/Ragnarok Agents/runtime'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_p1.py start --runtime 'D:/Ragnarok Agents/runtime'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/p1_nav.py --runtime 'D:/Ragnarok Agents/runtime' --x 95 --y 111 --timeout 45
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/p1_nav.py --runtime 'D:/Ragnarok Agents/runtime' --x 45 --y 100 --timeout 45 --cancel-after 2
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_p1.py stop --runtime 'D:/Ragnarok Agents/runtime'
```

Coordinates are on the start map `new_1-1`; same-map destinations only.

Native combat, pickup and local recovery (P1b) on the same profile, with Tarin on
`prt_fild08` ([evidence and test placement](docs/evidence/P1b-native-combat.md)):

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/p1_hunt.py --runtime 'D:/Ragnarok Agents/runtime' --probe --kills 6 --seconds 480
```

Cross-map travel through free walk portals only (no Kafra/paid/NPC warps) and a
bounded NPC dialog (P2a), same profile, Tarin starting on `prt_fild08`
([evidence and limits](docs/evidence/P2a-portal-travel-npc.md)):

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/p2_trip.py --runtime 'D:/Ragnarok Agents/runtime' --timeout 150 travel:prontera:157:31 talk:160:29:Cancel travel:prt_fild08:170:365 travel:geffen:120:100
```

Bounded NPC supply (P2b): a local, model-free decision from loot, weight, healing
and Zeny, then a walk-portal trip to sell loot and buy healing at the Prontera
Fruit Gardener ([evidence and limits](docs/evidence/P2b-npc-supply.md)):

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/p2_supply.py --runtime 'D:/Ragnarok Agents/runtime' --probe
```

## Continuous three-agent runtime (M4 continuation, Chat 06)

Use PowerShell from `D:/Ragnarok Agents/m4-continuous`. The existing M4 profiles,
local native server/database and Poring fixture must already be prepared. Start
reuses them and restarts only the three project clients to load current bridge
code and fresh inventories; it never resets characters, balances or memory.
Keep other gameplay controllers stopped: all worktrees share ports and runtime.

```powershell
Set-Location 'D:/Ragnarok Agents/m4-continuous'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' observe --seconds 5
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' say --sender agent --target third --text 'Name and one preference only, very briefly?'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' status
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' stop
```

`start` returns when startup status is published; wait for connected snapshots
and a hunt/rest phase in `observe`. It runs until `stop`; `run` is the foreground
alternative, and `--seconds N` requests a bounded development run. `stop`
requests durable cleanup; wait for `running: false` / `phase: stopped` in
`status` before starting again. Client/server processes stay up. A pending
inference call can delay cleanup up to its existing 60-second cold-service
timeout; an active client restart can take longer than a polling tick. A stale
status age indicates an exited/hung process or a lifecycle operation, not proof
of current connection. A second controller or direct M4 preparation fails its
ownership lock while this controller runs.

A GPU-telemetry failure pauses new actions and dialogue admissions, with one
retry after one second (each probe still has a three-second timeout). If the
retry fails, the controller fails closed. Fatal exits report `phase: failed`
and a typed `error` in status; normal cleanup reports `phase: stopped`.
RAM/GPU budgets remain unchanged.

Alden alternates solo and explicitly coordinated Poring hunts with Bram,
collects loot, and offers one Jellopy for ten Zeny every three successful hunts.
Mira patrols two nearby cells and can converse. Unaffordable trades or missing
goods are skipped until a later trade interval; balances are never replenished.
Unknown transfers survive stop/restart and are reconciled before any new
transfer. Ambiguity requires investigation; do not delete the ledger to bypass it.

The clients are **headless**. `observe` reads controller status without taking
a bridge connection. Full recent replies and snapshots are in `status`; bounded
events are in `runtime/m4/live/events.jsonl` plus three rotated segments.
`say` sends ordinary public chat **from the selected existing test character**;
it is a manual headless interaction path, not a separate human account. Names:
`agent` = M4 Alden, `peer` = M4 Bram, `third` = M4 Mira. Sender and target must
differ. Queued input expires after 30 seconds. At most one inference turn per
identity is admitted, with a ten-second admission interval; busy prompts can
be skipped. From a compatible graphical player near the square, the addressed
syntax is `M4:third:Hello` (or `agent` / `peer`). A graphical client, lawful game
assets, matching protocol `20130807` and a separate player account are **not
supplied or verified** by this slice. The proven interaction path is headless.

Selected-model conversation needs the existing Ollama service on 11434; the
fixed `web poring` prompt also needs existing SearXNG on 8080. If starting Ollama
manually in this environment, the shell has a stale model-store variable. These
commands start the installed server using the existing user-configured store
without changing global settings; use them only when its listener is absent:

```powershell
$env:OLLAMA_MODELS = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS','User')
Start-Process -FilePath 'C:/Users/azusu/AppData/Local/Programs/Ollama/ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden
```

The verified store is `D:/Local_AI/Models/Ollama`; no model download is needed.
If inference is unavailable, gameplay continues and addressed turns receive a
bounded fallback. After a 30-second circuit cooldown, a new turn can try again;
old prompts and unknown game actions are never replayed. Search exports only
the existing fixed public query, with source attribution.

At this handoff Ollama/9B is available; SearXNG is offline because the existing
Docker Linux backend did not start. `web poring` currently delivers a fallback.
No search container was created or reconfigured.

This remains the controlled Prontera fixture: local routing, a stationary
Poring with a guaranteed Jellopy, fixed roles/offers and three novices. The short
checks do not establish unattended long-duration reliability or full M4 acceptance.

## Three-agent functional prototype (M4)

These earlier commands run finite scripted demonstrations. Stop the continuous
controller before using them.

Use PowerShell from `D:/Ragnarok Agents/m4-worktree`, with the existing native
server/database, Ollama and SearXNG available. These commands were verified:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_m4.py --runtime 'D:/Ragnarok Agents/runtime' --start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode all
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode web
```

Preparation adds three ordinary test novices and a local stationary Poring
fixture, then restarts the project map server and clients. It preserves existing
characters, balances, databases, profiles and M3 memory. The fixture gives a
labeled guaranteed Jellopy reward alongside normal drops. Alden leads/gathers,
Bram flanks/strikes, and Mira converses. The fixed trade exchanges one earned
Jellopy for ten Zeny; repeated demonstrations consume the buyer's existing
Zeny. Nothing replenishes balances automatically.

Watch the terminal for per-action server results; each run prints its evidence
directory and a final JSON summary. A successful combined run reports
`functional_complete: true`. The clients are headless, so observation is through
these normalized events and retained evidence. For snapshots only:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode observe --seconds 2
```

Run only one controller/observer at a time: each bridge allows one authenticated
consumer. Directed `M4:agent:`, `M4:peer:` and `M4:third:` prompts admit a bounded
reply; ordinary replies never start another turn. Only `web poring` selects the
fixed public query. The runner ends after its scenario; it is not a persistent
unattended population service. Server/client processes remain available.

This fault command deliberately exits with code 1 after final trade packets.
The following command reconciles the unknown transfer from fresh client
inventories plus read-only server persistence, without starting a new transfer:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade --trade-fault after_commit_exit
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade
```

The current project clients occupy loopback bridges 8765, 8766 and 8767. M1
profiles and characters remain preserved; M4 preparation replaces their client
processes on the first two ports. Unknown/ambiguous transfers block later
transfers until reconciled. This controlled prototype does not establish full
M4 social acceptance, general navigation or the one-hour stabilization target.
