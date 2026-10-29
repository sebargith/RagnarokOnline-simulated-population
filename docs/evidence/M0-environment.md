# M0 - Environment audit

Audited 2026-10-29 (America/Santiago), from PowerShell 7.6.5 at `D:\Ragnarok Agents`. Linux probes used `wsl -d Ubuntu` and Bash. This is inspection evidence and a proposed M1 procedure, not an installation or compatibility result. No dependencies/models were installed or downloaded; no game service was started.

## Verified environment

| Check | Observed result |
| --- | --- |
| Windows / chassis | Windows 11 Home Single Language, 10.0.26200 (WSL reports build 26200.9457); Lenovo 82N6 |
| CPU / host RAM | Ryzen 9 5900HX, 8 cores / 16 threads; 31.86 GiB visible RAM, 11.17 GiB free at the probe |
| GPU / driver | RTX 3080 Laptop, driver 591.59; 16,384 MiB total, 1,543 MiB used, 14,633 MiB free |
| WSL | 3.0.3.0; kernel 6.18.54.1-microsoft-standard-WSL2; Ubuntu and docker-desktop already running as WSL2 distros |
| Ubuntu | 22.04.4 LTS (jammy), user `seba57`; systemd PID 1 and enabled in `/etc/wsl.conf` |
| WSL RAM / GPU | About 15 GiB visible / 13 GiB available; 4 GiB swap unused; GPU query succeeds with 16,384 MiB total / 14,624 MiB free |
| C: | NTFS, 952.62 GiB total / 175.46 GiB free |
| D: | NTFS, 1,863.00 GiB total / 44.64 GiB free |
| Ubuntu storage | Registry BasePath is on C: under Ubuntu's package `LocalState`; Linux `df` reports a virtual 1,007 GiB filesystem / 919 GiB available |

The virtual WSL capacity does **not** override physical C: free space. RAM/GPU samples are snapshots at different instants, not additive reservations or performance measurements. No Windows user `.wslconfig` was found. The user-reported Legion marketing model was not independently resolved.

| Surface | Installed tools and gaps |
| --- | --- |
| Windows | Git 2.47.1.windows.1, default Python 3.13.3. `py --list-paths` also registers 3.12/3.11/3.10/3.8/2.7; these other interpreters were not executed. |
| Existing optional tools | CUDA compiler 12.3.52; Docker Desktop 4.54.0 / Engine 29.1.2 responds. Neither is needed for the proposed M1 build. |
| Ubuntu toolchain | Git 2.34.1, GCC/G++ 11.4.0, Make 4.3, CMake 3.22.1; build-essential 12.9ubuntu3 and zlib1g-dev 1:1.2.11.dfsg-2ubuntu9.2 installed. |
| Ubuntu Python | 3.10.12; `socket`, `sqlite3`, `venv` import; SQLite 3.37.2. `python3.10-venv` 3.10.12-1~22.04.18 installed; ensurepip reports pip 22.0.2. The absent `python3-venv` metapackage is unnecessary here. Unversioned `python` is absent. |
| Ubuntu Perl | 5.34.0; threads enabled; Time::HiRes, IO::Socket::INET, JSON::PP, threads and Compress::Zlib load. Compress::Zlib 2.102; Perl CORE headers present. `libperl-dev` metapackage absent; actual XSTools linking remains untested. |
| Missing M1 packages | `mariadb-server`, `libmariadb-dev`, `libmariadb-dev-compat`, `libreadline-dev`, `libcurl4-openssl-dev`. MariaDB/MySQL commands and active services absent. |
| Listeners | Windows 127.0.0.1:11434 (Ollama) and 127.0.0.1:8080 (Docker backend) occupied; WSL also reports 127.0.0.1:8080. No listeners on 3306/6900/6121/5121 in either view. This is not a connectivity test. |

## Bounded asset inventory

Windows Ollama **0.40.12** responds; `ollama ps` showed no loaded model. Useful M2 reuse candidates from its local inventory:

| Existing tag | Local ID | CLI size |
| --- | --- | --- |
| `qwen3.5:4b` | `d8b0f5e9760c` | 3.3 GB |
| `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K` | `77beda99ef49` | 8.9 GB |
| `gpt-oss:20b` | `17052f91a42e` | 13 GB |

Other tags include 27B quantizations around 11-15 GB. Sizes/IDs are the CLI's inventory, not fit or quality results. No model was loaded, selected, or benchmarked.

Preserve existing stores: the shell's `OLLAMA_MODELS` names a nonexistent `D:\Local AI\Ollama\models`, while the user-level variable names the existing `D:\Local_AI\Models\Ollama`. `D:\Ollama\models` and the default Windows `.ollama\models` also exist. The running server's actual backing store was not established; resolve this before any M2 download or move.

Search covered repository files and its `vendor`, `models`, `runtime` paths; immediate C:/D: directory names matching rAthena/OpenKore/Ragnarok/Ollama/models; exact C:/D: `rathena`/`openkore` paths; standard model-cache indexes; and WSL paths `~/rathena`, `~/openkore`, `~/ragnarok-agents`, `~/Ragnarok Agents`, `~/projects/{rathena,openkore}`, `/opt/{rathena,openkore}`. No server/client checkout was found there. Hugging Face cache indexes exist on Windows/WSL; no additional text-model candidate was established. No unrelated personal folders or model-weight contents were searched. A graphical RO client elsewhere on disk remains unknown.

## Git and setup review

- Starting state: unborn `main`, zero commits/tracked files, seven untracked setup files: `.gitignore`, `AGENTS.md`, `README.md`, and four documents under `docs/`.
- `origin`: `https://github.com/sebargith/RagnarokOnline-simulated-population.git`. `git ls-remote --heads origin` succeeded with no advertised branch heads; configured `origin/main` unavailable locally. No fetch, push, reset, or remote mutation performed.
- Existing effective author: `sebargith <131008747+sebargith@users.noreply.github.com>`, from the user Git configuration. No global settings changed.
- Reviewed all seven setup files. Updated README/architecture/handoff with M0 findings; removed CURRENT_STATE's broken reference to an absent reusable preparation kit; added local database/journal/log ignore patterns. Milestone scope and repository instructions remain unchanged.
- The authorized initial commit contains only reviewed setup files and this evidence. Its ID is recorded in local Git history; nothing is published.

## Recommended M1 setup

Use the **existing Ubuntu distro**, without Docker, for one MariaDB instance, rAthena login/character/map servers, one headless OpenKore client, and one Python bridge process. Keep this Git checkout on D:. Store external sources/builds, Linux venv and runtime files under `/home/seba57/ragnarok-agents/` on Ubuntu's native filesystem; package-managed MariaDB data stays at `/var/lib/mysql`. Both consume C: capacity. This follows [Microsoft's WSL filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).

| Component | Candidate, not runtime-validated |
| --- | --- |
| rAthena | `d4b8e7b8f16061cc2496d377ac8f777ce72a4f39` (master observed with `git ls-remote`), pre-Renewal, protocol `20130807` |
| MariaDB | Local jammy candidate `1:10.6.23-0ubuntu0.22.04.1`; refresh/recheck before install, then record exact installed versions |
| OpenKore | `e0b04ee7090ff0bc9ab0fa6b876756c4b9004770` (master observed with `git ls-remote`), direct/headless mode, `serverType kRO_RagexeRE_2013_08_07a` |
| Bridge | Existing Ubuntu Python 3.10.12 / Perl 5.34; a small project-owned OpenKore plugin and local IPC, still to be built/proven |
| Inference | None for M1. Windows Ollama/model reuse is an M2 candidate; WSL access to its loopback endpoint is untested. |

**Protocol evidence only:** rAthena's [20130807 table](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/src/map/clif_shuffle.hpp#L317) and OpenKore's [send module](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Network/Send/kRO/RagexeRE_2013_08_07a.pm) both specify map login `0x022D` and movement `0x0437`; a [receive module](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Network/Receive/kRO/RagexeRE_2013_08_07a.pm) exists. Its `RagexeRE` name does not select server gameplay rules. Matching these IDs does not prove full packet compatibility.

OpenKore itself is the M1 game client. Use a temporary second headless test account/client for chat and independent movement observation, without adding another persistent agent. rAthena supplies a [default map cache](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/doc/map_cache.txt); OpenKore's tree includes fields for `prontera`, `payon`, and `prt_fild08`. This supports trying a stock-map proof without a graphical asset download; field/cell agreement remains untested.

### Downloads and space

| Item | Known size or planning allowance | Destination |
| --- | --- | --- |
| Five missing packages plus dependencies | Read-only apt simulation: **21 new**, 0 upgraded/removed, 54 not upgraded. Exact candidate metadata totals **20,535,446 bytes / 19.58 MiB** download and **168.91 MiB** installed package files; excludes DB initialization, index refresh, logs. | Ubuntu package paths on C: |
| Pinned rAthena source | Complete GitHub tree blob-size sum: 93.6 MiB. Compressed Git transfer unknown. | `~/ragnarok-agents/vendor/rathena` |
| Pinned OpenKore, bundled fields/deps/SCons | Complete tree blob-size sum: 200.5 MiB. Compressed Git transfer unknown. | `~/ragnarok-agents/vendor/openkore` |
| Builds, venv, DB, bounded traces | Reserve **5 GiB on C:** for M1; planning allowance, not a measured footprint. Start builds with two jobs. | Linux runtime/venv and `/var/lib/mysql` |
| Graphical client / new models | **0 required by this M1 plan**. Graphical-client size unknown until an asset is selected; no model download belongs to M1. | Deferred |

Apt indexes were dated 2026-10-28 except base jammy. No `apt update` ran. Size totals use `apt-cache show package=version` for the exact simulated packages; installed-size sums are not measured net disk growth. Recheck candidates and sizes after refreshing metadata; do not freeze an older security package to preserve this estimate.

### Proposed M1 procedure - not executed

1. **Dependencies:** enter `wsl -d Ubuntu` / Bash and recheck storage/RAM. Refresh apt metadata only in M1, simulate the five-package set again, review changes, install it and record `dpkg-query` versions. Reuse Python's existing version-specific venv support; no new Python/CUDA/Docker/inference runtime is needed.
2. **Sources/build:** create `~/ragnarok-agents/{vendor,runtime}`; clone upstream repositories there and check out the candidate SHAs. For rAthena, try the source-supported `./configure --enable-prere --enable-packetver=20130807`, then `make -j2 login char map`. For OpenKore, invoke `python3 src/scons-local-3.1.2/scons.py` directly: its Makefile assumes the absent `python` command and can print a failure while returning success. Check build status, artifact and launch version explicitly.
3. **Local server:** initialize the pinned SQL schema/required pre-Renewal data with an application DB account and non-default inter-server credentials. Keep real secrets/configuration outside Git; retain sanitized templates/version manifests. Bind DB/game services and advertised character/map addresses to loopback (3306/6900/6121/5121), and verify actual bindings. Explicitly align unencrypted packet handling for this local test: rAthena enables obfuscation by default for this date; inspect its custom post-defines and verify the effective build.
4. **Compatibility gate:** configure a private local OpenKore profile; verify serverType, receive tables, login version/master_version, character-block format and encoding against source/observed packets. Disable automatic public-server selection. On one stock map, verify login, position/HP/inventory/nearby-player decoding, field dimensions/walkable cells, observed movement and a simple gameplay routine. Save source/config hashes and decoded-event evidence. Diagnose a mismatch before bridge work; no unplanned general-purpose client replacement.
5. **Bridge proof:** create the venv under `~/ragnarok-agents`; add a project-owned plugin using [OpenKore hooks](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Plugins.pm) plus a nonblocking local Unix socket and restricted JSON schema. Permit bounded movement and ordinary public chat; reject arbitrary console/admin commands, malformed/oversized input and stale/disconnected requests; recheck live state before execution. Start with one in-flight action, a finite event queue and explicit overflow/resync, deadlines and request/session IDs. Confirm movement from observed position and chat from the test peer; sending a packet alone is not completion. Timeout means unknown until reconciled, with no automatic chat resend.
6. **Acceptance:** run M1's 10-minute connection, movement/routine, bidirectional chat, Python observation/validated action, invalid/stale command, and forced disconnect/reconnect checks. Bound reconnect attempts/backoff and verify no duplicate side effects. Record actual commands, pins, bindings, resource use, failures and concise evidence; only then add working commands to README and commit M1. No inference/social-memory work yet.

Supporting source inspected: [rAthena configure options](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/configure.ac), [packet defaults](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/src/config/packets.hpp), [Make targets](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/Makefile.in), [OpenKore build wrapper](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/Makefile), and [Linux CI dependencies](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/.github/workflows/build_XSTools.yml). These support a candidate procedure, not a local build result. Broader model research and alternative frameworks/distributions were outside the audit decision.

## Choices and limits

- Accept or adjust the WSL/headless layout by starting assignment 02. No hardware purchase, new model or paid service is proposed.
- Reversible defaults: English test messages, stock pre-Renewal rules/rates, one shared stock test map. An exact historical episode requires a content decision before customization; pre-Renewal mode alone does not establish an episode.
- If a Windows graphical client is required in M1, identify its folder/executable date/data first. Protocol/hash, download size, Windows-to-WSL connectivity and rendering tests then become additional work. No graphical asset was selected.
- Build/protocol/bridge behavior, resource use under gameplay load and M2 quality remain unverified. M0 completion does not start M1.

## Inspection and validation record

Commands actually run; outputs are summarized above, with no raw personal inventory/log dump committed:

- **Git / repository, PowerShell:** `git status --short --branch`, `git ls-files --others --exclude-standard`, `git log -1` (expected unborn-branch failure), `git remote -v`, `git config --show-origin --get user.name`, `git config --show-origin --get user.email`, `git ls-remote --heads origin`, `git ls-remote <upstream-url> refs/heads/master`; `rg --files --hidden -g '!.git/**'`. All seven setup files read/reviewed.
- **Windows:** `Get-CimInstance` for Win32_OperatingSystem/Processor/ComputerSystem; `Get-Volume`; relevant `Get-Command`, installed-app/WSL-registry `Get-ItemProperty`, bounded `Test-Path`/`Get-ChildItem`, targeted `Get-Process`/`Get-NetTCPConnection`; `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free --format=csv,noheader`; `wsl --version`, `wsl --status`, `wsl --list --verbose`; `git --version`, `python --version`, `py --list-paths`, `ollama --version`, `ollama list`, `ollama ps`, `docker version --format '{{json .}}'`, `nvcc --version`.
- **Ubuntu Bash:** `cat /etc/os-release`, `uname -r`, `id -un`, `free -h`, `df -h / /mnt/c /mnt/d`; relevant `command -v`/version and `dpkg-query -W` probes; Python stdlib/ensurepip and Perl modules/headers; `ps -p 1 -o comm=`, `cat /etc/wsl.conf`, `/usr/lib/wsl/lib/nvidia-smi`, filtered `ss -ltn`, `systemctl is-active mariadb mysql`; bounded path/cache indexes; `apt-cache policy`; `apt-get --simulate --no-install-recommends install mariadb-server libmariadb-dev libmariadb-dev-compat libreadline-dev libcurl4-openssl-dev`, then `apt-cache show` for exact simulated versions to sum Size/Installed-Size.
- **Probe corrections:** initial PowerShell-to-Bash stdin probes appended CR to the final argument, causing an `ss` parse error and false package-not-found result; corrected probes succeeded. A separate native-argument Perl probe was rerun successfully through Bash. Conclusions use corrected results.
- **Upstream research:** linked documentation/source and recursive GitHub trees at the two SHAs read through web/GitHub tools. Both trees reported `truncated: false`; summed blob sizes exclude Git history and are not transfer measurements. No source checkout/archive or model weight downloaded.
- **Documentation checks passed:** a Python stdlib script checked 17 local Markdown targets and balanced fences in seven Markdown files; `git check-ignore --no-index -q -- <path>` passed 18 positive/negative cases. `git diff --cached --check` passed, and every staged file was reviewed with `git diff --cached -- <paths>` (eight files total). `git diff --exit-code` found no unstaged edits at review. No application/gameplay/inference tests ran; no application runner exists.
