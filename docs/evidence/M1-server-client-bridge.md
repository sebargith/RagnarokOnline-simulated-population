# M1 - Native server/client bridge

Executed 2026-10-29 (America/Santiago), using PowerShell 7 at `D:\Ragnarok Agents`. The user approved M0's native Windows setup and assignment 02. No WSL/Docker, graphical client, model download, service installation, global PATH change or push was used.

## Installed and built

| Component | Actual result |
| --- | --- |
| rAthena | `d4b8e7b8f16061cc2496d377ac8f777ce72a4f39`; Release x64 login/char/map builds passed with VS 2019 Build Tools 16.11/MSVC v142 and Windows SDK 10.0.19041.0. |
| Rules/protocol | Custom pre-defines `PRERE`, `PACKETVER 20130807`; post-defines disable packet obfuscation. Server startup reports packet version `20130807` and obfuscation disabled. |
| MariaDB | Portable 10.11.19 x64 ZIP, 93,557,290 bytes; official SHA-256 matched. Project-local database initialized; pinned `main.sql`, `web.sql`, `roulette_default_data.sql`, `logs.sql` imported. Application account has SELECT/INSERT/UPDATE/DELETE on the game schema. |
| OpenKore | `e0b04ee7090ff0bc9ab0fa6b876756c4b9004770`; portable Strawberry Perl 5.32.1.1 x86, ZIP 154,581,246 bytes; official SHA-256 matched. Bundled SCons 3.1.2 built matching x86 XSTools; launch/version and gameplay passed. |
| Client profile | `kRO_RagexeRE_2013_08_07a`, matching date's receive table before generic kRO tables; version `30`, master version `1`, Western wire encoding, 144-byte character blocks, direct mode. |
| Python/bridge | Existing Python 3.11.9 x64 in `.venv`; project-owned authenticated loopback plugin, headless adapter and stream client. No pip dependency required. |

PE headers verified `0x8664` for MariaDB/map-server and `0x014c` for Perl/XSTools. Native builds, DLL loading and gameplay worked in the path with spaces; no drive alias was needed. Sources/builds/portable tools are under `vendor/`, secrets/configuration/data/logs under `runtime/`. Measured file bytes: vendor 2.308 GiB, runtime 0.240 GiB, venv 0.022 GiB; this is not allocated disk usage. D: free space was 44.64 GiB at start and 40.93 GiB at an intermediate probe; free-space changes are not a project footprint measurement.

Both archive checksums were obtained from the publishers: [MariaDB manifest](https://archive.mariadb.org/mariadb-10.11.19/winx64-packages/sha256sums.txt) and [Strawberry release metadata](https://strawberryperl.com/releases.json). Pins and URLs are tracked in [versions.json](../../config/versions.json); hashes of tested binaries/configs/source are in [M1 manifest](M1-manifest.json).

## Acceptance results

The fixed target before the final duration run was **600 uninterrupted seconds**, unchanged game sessions and **no snapshot gap above five seconds**. The live command was `& .\.venv\Scripts\python.exe scripts/accept_m1.py --seconds 600` with both fixture clients started.

| Acceptance check | Actual evidence/result |
| --- | --- |
| Setup/start/stop | Native dependency acquisition/checksums, build, configuration, one-time DB initialization, repeated start/stop, client launch and read-only observation commands executed. README records the commands; BRIDGE records schemas and troubleshooting. |
| Login/perception | Both ordinary novice accounts logged in on Prontera. Scoped snapshots decoded `150,180` / `152,180`, HP `42/42`, three item `501` potions, the other visible player, and field dimensions `312 x 392`. |
| Ten-minute gameplay | Run `20261029T162200Z`: **600.031 s** continuously connected; ten adjacent-cell round trips `150,180 -> 151,180 -> 150,180`. Maximum snapshot gap **1.033 s**. Main client emitted 616 snapshots and 22 movement acknowledgments over the whole scenario; peer emitted 619 snapshots. |
| Python control/confirmation | Python submitted validated movement; server `0087` acknowledgment matched the requested destination, then the independent peer's perception matched it. `completed` means movement acknowledgment, not an arrival claim. |
| Chat/duplicates | Main client sent `M1 bridge proof 20261029T162200Z`; peer received it once and replied. Both server echo and independent received chat were retained. Resending the same bridge request ID returned cached completion and caused no second delivery. |
| Invalid/failed input | Console action, command-prefixed chat, newline chat, distant/wrong-map movement, stale session and expired deadline produced explicit rejection. Wrong token, 4,097-byte input and malformed JSON closed the stream; reauthentication/resync succeeded. |
| Disconnect/reconnect | Real map-server SIGINT shutdown, five-second outage, then restart. Both clients reconnected in new game epochs. Outage chat was rejected as `disconnected`; an old-epoch proposal was rejected as `stale_session`. Confirmed post-reconnect chat completed the check in **14.093 s** including that chat. No automatic action resend. |

The full run's summary has `passed: true`. Raw retained evidence is ignored: `runtime/evidence/20261029T162200Z/{summary.json,observations.ndjson}`. The trace contains normalized source events, action results and independent peer observations; game service/client logs remain under their documented runtime paths.

Final review corrected a parser edge case: buffered frames after the fourth could wait for another socket read. The fix parses up to four buffered frames on every game tick. On a fresh peer, `scripts/check_bridge_faults.py` passed five coalesced frames without further writes, retained all 128 request IDs, rejected a 129th action, and replayed the oldest cached ID without execution. Evidence: `runtime/evidence/framing-cache-regression.json`. This fixture deliberately exhausts that peer's action budget; it was restarted afterward.

A subsequent five-second live scenario passed on the final framing code after an executed `m1.py build` and complete server/client restart: run `20261029T163521Z`, 5.015 s connected, maximum snapshot gap 1.029 s, all seven scenario groups passed, final outage/reconnect/chat check 27.281 s. Its summary/trace remain under that run's ignored evidence directory. The ten-minute run preceded the targeted framing correction; it is not presented as a second ten-minute run on the amended parser.

Seven Python unit checks passed (`-m unittest discover -s tests -v`): stale/disconnected proposals, explicit invalid overrides, a single transmitted frame without retry, fragmented/coalesced streams, cross-agent observation rejection, and bounded consumer queue overflow. Python compile checks and Perl syntax checks also passed.

During the uninterrupted trial, one Windows working-set sample totaled **635.62 MiB**: MariaDB 109.95, map 322.76, character 11.53, login 9.43, main client 90.95, peer 91.00 MiB. This excludes the short-lived Python process and is not a peak/load benchmark. All six actual listeners were `127.0.0.1` on ports 3306/6900/6121/5121/8765/8766; raw sample: `runtime/evidence/resources-continuous-trial.json`.

## Commands, corrections and limits

Commands actually executed include `py -3.11 -m venv .venv`; pinned `git clone --no-checkout --filter=blob:none` / `git checkout`; `Invoke-WebRequest`, `Get-FileHash`, `Expand-Archive`; MSBuild with `/t:server-components\login-server;server-components\char-server;server-components\map-server`, Release/x64/v142/19041 SDK and `/m:2`; `.venv\Scripts\python.exe src/scons-local-3.1.2/scons.py -j2`; native Perl `openkore.pl --version`; all documented `m1.py` setup/lifecycle commands; `observe.py`; five-second and 600-second acceptance commands; unit/compile/syntax checks; `Get-NetTCPConnection`, `Get-Process`, PE-header and file-size/hash probes. Actual wrapper build logs are `runtime/logs/{rathena-build,openkore-build}.log`.

Material integration corrections were retained in tooling:

- Unqualified MSBuild target names failed; solution-folder-qualified names built successfully.
- MariaDB's separate root TCP entry initially denied authenticated imports. The failed newly initialized directory was preserved as `runtime/mariadb/data-initialization-attempt-1`; the corrected initialization secures both local entries before importing.
- Initial 24-character inter-server passwords exceeded a native buffer's usable length; generated game/inter-server passwords are now 20 ASCII bytes. Existing fixture rows were corrected without exposing values.
- The generic kRO table failed at `082D`; the pinned date-specific table decoded it. The optional server PIN prompt is disabled for these fixtures.
- Redirecting the stock Windows console caused console-size warnings; the project headless adapter replaces only that interface. Portal compilation is disabled for adjacent-cell checks.
- An initial duration attempt (`20261029T162054Z`) failed before its continuous trial because the first connected snapshot preceded inventory/nearby-player packets. The harness now waits for decoded fixture data. Its `passed: false` summary is retained; no duration criterion was relaxed. The earlier `20261029T161826Z` five-second run passed but was only a smoke check.

Stock modern features unsupported by the selected protocol emit disabling warnings. SCons warns that pywin32 is absent; both native build attempts completed without installing it. No map-server SQL/error entries were found in the inspected logs. This is a stock pre-Renewal proof, not an exact historical episode or global route/combat test. Inventory display names remain stock kRO; test dialogue is English. Durable action reconciliation, inference, memory, social quality, long-duration operation and population scaling remain later milestones. Retry exhaustion, artificial suppression of a game acknowledgment and output-buffer saturation were not separately fault-injected; their configured bounds do not substitute for executed results.

Repository validation passed: 27 local Markdown links, balanced code fences, 20 repository files scanned without finding generated secret values, six runtime/source ignore-rule probes, 18 matching manifest hashes, and Git whitespace checks. The final diff was reviewed, including all new files. `m1.py stop`/`status` completed and a listener query confirmed all six project ports were released.

At handoff the project test processes were stopped. The original uncommitted M0/Windows edits to `CODEX_WORKFLOW.md` and `M0-environment.md` were preserved and excluded from the M1 commit. README, architecture and current state incorporate the approved native layout plus M1's actual results. No remote publishing or later milestone work was performed.
