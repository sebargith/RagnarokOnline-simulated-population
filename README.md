# Ragnarok Online AI Agents

A local-first project for persistent, socially believable AI players on a classic/pre-Renewal Ragnarok Online private server. The first target is one autonomous player with grounded conversation and memory across restarts, followed by three to five distinct players.

**Status:** M0 environment audit is complete; its setup recommendation awaits user acceptance for M1. Game integration, orchestration, inference benchmarks, and automated tests have not been implemented.

## Start here

Open the existing **Ragnarok Agents** local project in Codex, rooted at `D:\Ragnarok Agents`. Review the [M0 findings and proposed M1 procedure](docs/evidence/M0-environment.md), then use **02 - Server and client bridge** in [the Codex workflow](docs/CODEX_WORKFLOW.md) when accepting that setup.

- [General development rules](AGENTS.md)
- [Provisional architecture](docs/ARCHITECTURE.md)
- [Milestones and acceptance criteria](docs/ROADMAP.md)
- [Verified current state and next action](docs/CURRENT_STATE.md)

## Setup and operation

No installation, run, or application-test commands have been validated yet. M0 records inspection commands and an unexecuted M1 procedure; M1 adds verified server/client setup and troubleshooting; M2 adds inference commands; M3 adds the agent runner and relevant tests. Record the working directory and shell for every command, especially across Windows and WSL.

The recommended M1 layout uses the existing WSL2 Ubuntu 22.04 environment for pre-Renewal rAthena, MariaDB, one headless OpenKore client, and Python. Candidate source revisions, protocol date, missing packages, storage locations, and compatibility gates are in the M0 evidence. Installed Windows Ollama models may be reused in M2; no inference runtime or model download is needed for M1. This combination has not been built or connected yet.

Keep runtime data in ignored locations; keep scripts, configuration templates without secrets, compact experiment results, and version pins in Git. See [.gitignore](.gitignore).
