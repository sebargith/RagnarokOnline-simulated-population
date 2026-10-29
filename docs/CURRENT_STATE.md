# Current state

Updated: 2026-10-29 (America/Santiago).

## Verified

- M0 audit is complete. [Environment evidence](evidence/M0-environment.md) records commands, versions, bounded asset checks, download estimates, limitations, and the proposed M1 procedure.
- Windows 11 / WSL2 Ubuntu 22.04.4 work. Ryzen 9 5900HX, 31.86 GiB system RAM, and RTX 3080 Laptop with 16 GiB VRAM were verified; the NVIDIA GPU query also works inside WSL. CUDA computation was not tested.
- WSL already has GCC/G++, Make, Perl 5.34, Python 3.10.12 with usable venv support, and zlib headers. MariaDB and the selected database/readline/curl development packages are missing. The read-only package simulation resolved successfully.
- C: had 175.46 GiB free; D: had 44.64 GiB free. Ubuntu's VHD is backed by C:. Its virtual free capacity is not additional physical storage.
- Windows Ollama 0.40.12 responds and lists existing models; none was loaded by this audit. No rAthena/OpenKore installation was found in the bounded locations inspected. A graphical RO client was not identified.
- The initial repository contained seven untracked setup files and no commits. The remote advertised no branch heads. Git author identity is configured; no global settings were changed.
- Setup review removed a stale reference to an absent preparation kit and added local database/log ignore rules. Validation passed: 17 local Markdown links, balanced fences across seven Markdown files, 18 ignore-rule cases, and staged whitespace/full-diff review across all eight setup/evidence files. There is no application test runner.
- No dependencies were installed, models downloaded, game services started, or M1 application code implemented during M0. No push was performed.

## Recommendation awaiting acceptance

Use the existing Ubuntu distro for rAthena + MariaDB + one headless OpenKore client + Python. Keep external builds/runtime data under `/home/seba57/ragnarok-agents`; keep this Git checkout at `D:\Ragnarok Agents`. Candidate protocol is `20130807`, with exact upstream source revisions recorded in M0 evidence. Source inspection supports trying this combination; runtime compatibility is unproven.

## Blockers and limits

- M1 needs the documented packages and external source checkouts. Package candidates must be rechecked after refreshing apt metadata.
- rAthena/OpenKore build, packet decoding, maps, observations/actions, 10-minute connection, chat, and reconnect/failure checks have not run. No external bridge exists yet.
- A Windows graphical client adds an asset/version decision if requested; the proposed M1 uses OpenKore as its client and a temporary test peer for chat verification.
- Model fit, social quality, throughput, and the Windows Ollama-to-WSL boundary remain M2 work. No model was selected.

## Next action

Review the M0 recommendation, then start **02 - Server and client bridge** from [CODEX_WORKFLOW](CODEX_WORKFLOW.md) to accept it or state an adjustment. The first M1 step is to recheck disk space/package candidates and prepare the documented WSL dependencies and pinned sources. M1 has not started.
