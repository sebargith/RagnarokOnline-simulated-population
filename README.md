# Ragnarok Online AI Agents

A local-first project for persistent, socially believable AI players on a classic/pre-Renewal Ragnarok Online private server. The first target is one autonomous player with grounded conversation and memory across restarts, followed by three to five distinct players.

**Status:** M1 passed. The user selected the local Qwen3.5 9B Q6_K model after M2 measurement and stopped further model comparison. A standalone 9B turn can now call the existing local SearXNG service for public web search. Human dialogue quality remains unverified; no persistent social agent exists yet. See [current state](docs/CURRENT_STATE.md).

## Start here

Open the existing **Ragnarok Agents** local project in Codex, rooted at `D:\Ragnarok Agents`. Read the [user direction guide](docs/USER_GUIDE.txt) for status, chats and prompts; use the [current state](docs/CURRENT_STATE.md) for the verified handoff and [bridge contract](docs/BRIDGE.md) for M1 operation.

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

The existing self-hosted SearXNG container serves JSON search on `127.0.0.1:8080`. The model uses Ollama's local tool-call API; Python validates one search request, queries SearXNG, and returns at most three short, source-linked snippets. Search results are external claims and never establish game actions or rAthena state. This standalone turn is not yet connected to the game agent.

With SearXNG and Ollama running, this command was verified:

```powershell
& .\.venv\Scripts\python.exe scripts/ask_9b.py 'Search the web for the iRO Wiki Prontera page and tell me its URL.'
```

The endpoint and limits are in [web-search configuration](config/web-search.json). SearXNG needs no API key, but sends public queries to its configured internet search engines. If the local service is unavailable, the turn reports the failure. M3 must connect this tool through identity-scoped context and keep search failure from stopping routine gameplay.
