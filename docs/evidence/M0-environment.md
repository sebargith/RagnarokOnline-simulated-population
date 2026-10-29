# M0 - Environment audit

Audited 2026-10-29 (America/Santiago), from PowerShell 7.6.5 at `D:\Ragnarok Agents`. Linux probes used `wsl -d Ubuntu` and Bash. This is inspection evidence and a proposed M1 procedure, not an installation or compatibility result. No dependencies/models were installed or downloaded; no game service was started.

**Deployment decision updated 2026-10-29:** the user selected native Windows, preferably with new project dependencies and runtime data inside this directory. The Windows plan below supersedes the original WSL recommendation in commit `af543a3`. Original Windows/WSL observations remain audit history; Linux packages/commands are not prerequisites for the selected setup. This documentation revision does not start M1.

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
| Windows | Git 2.47.1.windows.1, default Python 3.13.3. `py --list-paths` also registers 3.12/3.11/3.10/3.8/2.7. The native follow-up executed 3.11.9 x64 successfully; other listed interpreters were not tested. |
| Existing optional tools | CUDA compiler 12.3.52; Docker Desktop 4.54.0 / Engine 29.1.2 responds. Neither is needed for the proposed M1 build. |
| Ubuntu toolchain | Git 2.34.1, GCC/G++ 11.4.0, Make 4.3, CMake 3.22.1; build-essential 12.9ubuntu3 and zlib1g-dev 1:1.2.11.dfsg-2ubuntu9.2 installed. |
| Ubuntu Python | 3.10.12; `socket`, `sqlite3`, `venv` import; SQLite 3.37.2. `python3.10-venv` 3.10.12-1~22.04.18 installed; ensurepip reports pip 22.0.2. The absent `python3-venv` metapackage is unnecessary here. Unversioned `python` is absent. |
| Ubuntu Perl | 5.34.0; threads enabled; Time::HiRes, IO::Socket::INET, JSON::PP, threads and Compress::Zlib load. Compress::Zlib 2.102; Perl CORE headers present. `libperl-dev` metapackage absent; actual XSTools linking remains untested. |
| Ubuntu-only gaps (historical) | `mariadb-server`, `libmariadb-dev`, `libmariadb-dev-compat`, `libreadline-dev`, `libcurl4-openssl-dev`. These are outside the selected Windows setup. MariaDB/MySQL commands were absent on both PATHs; Ubuntu services inactive. |
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

## Native Windows follow-up

- `vswhere` found VS 2019 Build Tools **16.11.46**, VS 2022 Build Tools **17.13.4**, and VS 2022 Community **17.14.25**. Only the 2019 entry matched `Microsoft.VisualStudio.Component.VC.Tools.x86.x64`. Its MSVC directory is **14.29.30133**, x64 `cl.exe` file version **19.29.30159.0**, and MSBuild executes with version **16.11.2.50704**. No MSVC directories were found under the inspected 2022 installations. The compiler itself has not been run.
- Windows SDK include directories **10.0.10240.0**, **10.0.19041.0**, **10.0.20348.0** exist; `Windows.h` and x64 `kernel32.lib` were verified for **10.0.19041.0**. No compilation/link test ran.
- `py -3.11 --version` reports **3.11.9**. That interpreter is 64-bit and imports `venv`, `ensurepip`, and SQLite **3.45.1**. No environment was created.
- Standard `C:\Strawberry` Perl/gmake paths and `C:\Program Files\MariaDB 10.11` / `MariaDB 11.4` were absent. The earlier PATH/installed-app checks found no native Perl/MariaDB. Project `vendor`, `runtime` and `.venv` directories are absent.
- Follow-up free space: **C: 175.14 GiB; D: 44.64 GiB**. Project-local downloads/builds/data will consume D:. No files/tools/models were moved.

## Selected native Windows M1 setup

Use PowerShell at `D:\Ragnarok Agents` for one native MariaDB process, rAthena login/character/map servers, one headless OpenKore client and one Python bridge. Reuse installed system tools in place. Prefer portable dependency archives, explicit executable paths and process-local PATH changes. Start/stop MariaDB explicitly with the project; a Windows service is not the initial plan. WSL/Docker are outside this deployment.

All paths below are **proposed**, not created. They are relative to `D:\Ragnarok Agents` and already covered by `.gitignore`:

| Path | Contents |
| --- | --- |
| `vendor\rathena`, `vendor\openkore` | Pinned upstream checkouts, build outputs and required adjacent DLLs |
| `vendor\mariadb`, `vendor\strawberry-perl` | Portable Windows dependency binaries |
| `.venv` | Project Python environment based on the existing 3.11.9 interpreter |
| `runtime\mariadb` | Project-specific MariaDB `my.ini` and `data\` directory |
| `runtime\openkore`, `runtime\config`, `runtime\logs` | Per-client profiles, real configuration/secrets and bounded raw evidence; generated rAthena import configuration can also live in its ignored vendor tree |
| `vendor\ro-client` (optional) | Separately identified graphical game assets, if requested |

Keep project-owned code, sanitized templates and version manifests in tracked directories when implemented. Existing Git/Python/Visual Studio installations and Ollama/model stores stay where they are; a project-local venv references its base Python, and this plan does not imply every dependency becomes portable. Test the space in `D:\Ragnarok Agents` before relying on native build/portable tools. If a tool rejects it, first evaluate a temporary unused drive-letter alias to the same physical project directory; document the mapping and verify its resolved target. Do not silently rename/move the project or switch platforms.

| Component | Candidate, not runtime-validated |
| --- | --- |
| rAthena | `d4b8e7b8f16061cc2496d377ac8f777ce72a4f39` (master observed with `git ls-remote`), pre-Renewal, protocol `20130807` |
| rAthena compiler | Existing VS 2019 C++ tools / MSBuild 16.11, candidate Release x64 with v142 and SDK 10.0.19041.0. Pinned projects use `$(DefaultPlatformToolset)`; compile/link remains unproven. |
| MariaDB | **10.11.19 Windows x64 ZIP** candidate, project-local data and console process. Verify archive checksum and native runtime requirements in M1; SQL/authentication compatibility unproven. |
| OpenKore | `e0b04ee7090ff0bc9ab0fa6b876756c4b9004770` (master observed with `git ls-remote`), direct/headless mode, `serverType kRO_RagexeRE_2013_08_07a` |
| OpenKore Perl/build tools | **Strawberry Perl 5.32.1.1 portable 32-bit**, matching the pairing in pinned upstream Windows CI. Use its own compiler/tools and build a matching 32-bit XSTools; the existing Python 3.11.9 x64 is a candidate SCons driver, not an ABI-matched Perl DLL. This exact local combination is untested. |
| Bridge | Windows Python **3.11.9 x64** in `.venv`; project-owned OpenKore plugin with restricted loopback TCP JSON messages, still to be built/proven. Separate processes can differ in bitness; each native DLL must match its loading process. |
| Inference | None for M1. Existing Windows Ollama/model reuse remains an M2 candidate via local HTTP; endpoint integration and performance are untested. |

**Protocol evidence only:** rAthena's [20130807 table](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/src/map/clif_shuffle.hpp#L317) and OpenKore's [send module](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Network/Send/kRO/RagexeRE_2013_08_07a.pm) both specify map login `0x022D` and movement `0x0437`; a [receive module](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Network/Receive/kRO/RagexeRE_2013_08_07a.pm) exists. Its `RagexeRE` name does not select server gameplay rules. Matching these IDs does not prove full packet compatibility.

OpenKore itself is the M1 game client. Use a temporary second headless test account/client for chat and independent movement observation, without adding another persistent agent. rAthena supplies a [default map cache](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/doc/map_cache.txt); OpenKore's tree includes fields for `prontera`, `payon`, and `prt_fild08`. This supports trying a stock-map proof without a graphical asset download; field/cell agreement remains untested.

### Downloads and space

| Item | Known size or planning allowance | Destination |
| --- | --- | --- |
| MariaDB 10.11.19 x64 ZIP | Official file listing reports **93.6 MB**; expanded size/native runtime extras not measured. SHA-256 manifest retrieval failed through the web tool; checksum validation is still required before use. | `vendor\mariadb` |
| Strawberry Perl 5.32.1.1 32-bit portable ZIP | Official release metadata: **154,581,246 bytes / 147.42 MiB**; includes Perl and its compiler/tools. Expanded footprint not measured. | `vendor\strawberry-perl` |
| Pinned rAthena source | Complete GitHub tree blob-size sum: 93.6 MiB. Compressed Git transfer unknown. | `vendor\rathena` |
| Pinned OpenKore, bundled fields/deps/SCons | Complete tree blob-size sum: 200.5 MiB. Compressed Git transfer unknown. | `vendor\openkore` |
| Existing Git/Python/MSVC/SDK | Reuse in place; **0 planned download** if the selected native build works with them. Any missing DLL/runtime/tool component must be identified and sized in M1. | Existing system paths; project `.venv` references installed Python |
| Expanded tools, builds, venv, DB, traces | Reserve **8 GiB on D:** initially; planning allowance, not a measured footprint. Recheck free space before downloading; limit build parallelism initially. | Project `vendor`, `.venv`, `runtime` |
| Graphical client / new models | **0 required by this M1 plan**. Graphical-client size unknown until an asset is selected; no model download belongs to M1. | Deferred |

Native sources: [MariaDB ZIP listing](https://dlm.mariadb.com/browse/mariadb_server/10.11.19/winx64-packages/) and [Strawberry release metadata](https://strawberryperl.com/releases.json). Candidate Perl archive: `strawberry-perl-5.32.1.1-32bit-portable.zip`, SHA-256 `d9c5711d12573a0f6d977792caa58364b1d46217521ae5c25cf5cc378a7c23c0`. This legacy version is a bounded compatibility baseline from OpenKore's Windows CI, not a recommendation for unrelated projects. No binary archive was downloaded.

The earlier **Linux-only** apt simulation resolved 21 new packages, 20,535,446 bytes of downloads and 168.91 MiB of package files from local indexes, mostly dated 2026-10-28. That result is retained as history and is **not** a Windows download estimate or installation step. No `apt update` ran.

### Proposed M1 procedure - not executed

1. **Dependencies:** use PowerShell at `D:\Ragnarok Agents`; recheck D: capacity, ports and the native compiler/SDK/Python. When M1 is authorized, prepare `vendor`, `runtime` and `.venv` (candidate creation command `py -3.11 -m venv .venv`), acquire/checksum only the selected portable archives and extract into the proposed locations. Read each archive's setup instructions and test path-space handling/modules/native tools. Use process-local environment changes and explicit executable paths to avoid the existing MinGW/Python PATH mixtures. Verify requirements before adding any missing system runtime.
2. **Sources/build:** clone the two upstream repositories into `vendor` and check out the candidate SHAs. For rAthena, use Windows custom pre-defines `PRERE` and `PACKETVER 20130807`, then MSBuild's Release/x64 solution targets for login/char/map and their dependencies using the verified 2019 toolchain/SDK candidate. Record exact command/toolset/SDK, custom defines and required matching DB DLLs. For OpenKore, use the selected portable Perl/compiler environment and explicit `.venv\Scripts\python.exe` to drive bundled `src\scons-local-3.1.2\scons.py`; verify matching XSTools DLL build and launch. Its Makefile can hide a build failure behind an echo, so inspect actual exit status/artifacts. No Windows build command has been validated yet.
3. **Local server:** use the ZIP's `mariadb-install-db.exe` with an explicit project `runtime\mariadb\data` path, then run `mariadbd.exe` in console mode with the project `my.ini`; verify the exact version's options first. Keep credentials out of command histories/logs/Git, use an application DB account and non-default inter-server credentials, and import the pinned schema/required pre-Renewal data. Start/stop the project DB explicitly; do not install a service by default. Bind DB/game services and advertised character/map addresses to loopback (3306/6900/6121/5121), and verify actual bindings. Align unencrypted packet handling for this local test: rAthena enables obfuscation for this date, so inspect custom post-defines and verify the effective build.
4. **Compatibility gate:** configure a private local OpenKore profile; verify serverType, receive tables, login version/master_version, character-block format and encoding against source/observed packets. Disable automatic public-server selection. On one stock map, verify login, position/HP/inventory/nearby-player decoding, field dimensions/walkable cells, observed movement and a simple gameplay routine. Save source/config hashes and decoded-event evidence. Diagnose a mismatch before bridge work; no unplanned general-purpose client replacement.
5. **Bridge proof:** use project `.venv` Python and a project-owned plugin using [OpenKore hooks](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/src/Plugins.pm), with nonblocking TCP bound to `127.0.0.1` and a restricted framed JSON schema. Choose/check the bridge port in M1 and authenticate the local connection with a runtime token. Permit bounded movement and ordinary public chat; reject arbitrary console/admin commands, malformed/oversized input and stale/disconnected requests; recheck live state before execution. Start with one in-flight action, a finite event queue and explicit overflow/resync, deadlines and request/session IDs. Confirm movement from observed position and chat from the test peer; sending a packet alone is not completion. Timeout means unknown until reconciled, with no automatic chat resend.
6. **Acceptance:** run M1's 10-minute connection, movement/routine, bidirectional chat, Python observation/validated action, invalid/stale command, and forced disconnect/reconnect checks. Bound reconnect attempts/backoff and verify no duplicate side effects. Record actual commands, pins, bindings, resource use, failures and concise evidence; only then add working commands to README and commit M1. No inference/social-memory work yet.

Supporting native source inspected: [rAthena solution](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/rAthena.sln), [Windows project/toolset settings](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/src/login/login-server.vcxproj), [packet defaults](https://github.com/rathena/rathena/blob/d4b8e7b8f16061cc2496d377ac8f777ce72a4f39/src/config/packets.hpp), [OpenKore Windows CI](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/.github/workflows/build_XSTools.yml), [build wrapper](https://github.com/OpenKore/openkore/blob/e0b04ee7090ff0bc9ab0fa6b876756c4b9004770/Makefile), [MariaDB ZIP operation](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/installing-mariadb/binary-packages/installing-mariadb-windows-zip-packages) and [Windows DB initialization options](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/installing-mariadb/installing-system-tables-mariadb-install-db/mariadb-install-db-exe). These support a candidate procedure, not a local build result. No additional framework or model research was needed.

## Choices and limits

- Native Windows/project-local placement was selected by the user. Start assignment 02 when ready to implement it; this documentation revision authorizes no installation. No hardware purchase, new model or paid service is proposed.
- Reversible defaults: English test messages, stock pre-Renewal rules/rates, one shared stock test map. An exact historical episode requires a content decision before customization; pre-Renewal mode alone does not establish an episode.
- A graphical client remains optional: identify its executable date/data assets before including it in M1. Protocol/hash, download size and rendering tests then become additional work against the local Windows server. Choosing Windows does not settle this separate choice.
- Build/protocol/bridge behavior, resource use under gameplay load and M2 quality remain unverified. M0 completion does not start M1.

## Inspection and validation record

Commands actually run; outputs are summarized above, with no raw personal inventory/log dump committed:

- **Git / repository, PowerShell:** `git status --short --branch`, `git ls-files --others --exclude-standard`, `git log -1` (expected unborn-branch failure), `git remote -v`, `git config --show-origin --get user.name`, `git config --show-origin --get user.email`, `git ls-remote --heads origin`, `git ls-remote <upstream-url> refs/heads/master`; `rg --files --hidden -g '!.git/**'`. All seven setup files read/reviewed.
- **Windows:** `Get-CimInstance` for Win32_OperatingSystem/Processor/ComputerSystem; `Get-Volume`; relevant `Get-Command`, installed-app/WSL-registry `Get-ItemProperty`, bounded `Test-Path`/`Get-ChildItem`, targeted `Get-Process`/`Get-NetTCPConnection`; `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free --format=csv,noheader`; `wsl --version`, `wsl --status`, `wsl --list --verbose`; `git --version`, `python --version`, `py --list-paths`, `ollama --version`, `ollama list`, `ollama ps`, `docker version --format '{{json .}}'`, `nvcc --version`.
- **Ubuntu Bash:** `cat /etc/os-release`, `uname -r`, `id -un`, `free -h`, `df -h / /mnt/c /mnt/d`; relevant `command -v`/version and `dpkg-query -W` probes; Python stdlib/ensurepip and Perl modules/headers; `ps -p 1 -o comm=`, `cat /etc/wsl.conf`, `/usr/lib/wsl/lib/nvidia-smi`, filtered `ss -ltn`, `systemctl is-active mariadb mysql`; bounded path/cache indexes; `apt-cache policy`; `apt-get --simulate --no-install-recommends install mariadb-server libmariadb-dev libmariadb-dev-compat libreadline-dev libcurl4-openssl-dev`, then `apt-cache show` for exact simulated versions to sum Size/Installed-Size.
- **Probe corrections:** initial PowerShell-to-Bash stdin probes appended CR to the final argument, causing an `ss` parse error and false package-not-found result; corrected probes succeeded. A separate native-argument Perl probe was rerun successfully through Bash. Conclusions use corrected results.
- **Upstream research:** linked documentation/source and recursive GitHub trees at the two SHAs read through web/GitHub tools. Both trees reported `truncated: false`; summed blob sizes exclude Git history and are not transfer measurements. No source checkout/archive or model weight downloaded.
- **Original audit documentation checks passed:** a Python stdlib script checked 17 local Markdown targets and balanced fences in seven Markdown files; `git check-ignore --no-index -q -- <path>` passed 18 positive/negative cases. `git diff --cached --check` passed, and every staged file was reviewed with `git diff --cached -- <paths>` (eight files total). `git diff --exit-code` found no unstaged edits at that review.
- **Native Windows follow-up commands:** `git status --short --branch`, `git log -1 --oneline`, targeted `rg`/file reads; standard-path `vswhere.exe -all -products '*' -format json` and `-requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64` checks; bounded `Get-ChildItem` of the three discovered VS MSVC paths and SDK includes; `Get-Item` for the 2019 compiler/19041 SDK files; `MSBuild.exe -version -nologo`; `py -3.11 --version` and stdlib/bitness probe; exact dependency/project `Test-Path` checks and `Get-Volume`. Native source/docs/release metadata were inspected through GitHub/web tools; archive/checksum access failures are noted above. No binaries downloaded or environment/service/alias created.
- **Windows documentation revision validation passed:** 17 local Markdown targets, balanced fences in seven Markdown files, and 27 proposed native-path/regression ignore cases; `git diff --check` and full review of the five-file diff. A targeted search found no obsolete active Ubuntu deployment/Unix-socket instructions. No application/gameplay/inference tests ran; no application runner exists.
