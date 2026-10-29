# Current state

Updated: 2026-10-29 (America/Santiago).

## Verified

- **M1 passed.** [Actual results](evidence/M1-server-client-bridge.md), [tested hashes](evidence/M1-manifest.json), [commands](../README.md) and [bridge contract/troubleshooting](BRIDGE.md) carry the evidence and operating details. [M0](evidence/M0-environment.md) remains the historical environment audit.
- Native Windows rAthena `d4b8e7b8f16061cc2496d377ac8f777ce72a4f39`, pre-Renewal/protocol `20130807`, Release x64/v142/SDK 10.0.19041.0; portable MariaDB 10.11.19 x64; OpenKore `e0b04ee7090ff0bc9ab0fa6b876756c4b9004770` with Strawberry Perl 5.32.1.1 x86 and built matching XSTools; Python 3.11.9 x64. Both binary archives matched publisher SHA-256 values. The project path with spaces works without an alias.
- Duration run `20261029T162200Z` passed **600.031 s** continuously connected, ten movement round trips, maximum snapshot gap **1.033 s**, bidirectional chat, duplicate suppression, invalid/protocol rejection, and a real map-server shutdown/reconnect. The final reconnect/chat check took **14.093 s**.
- A final buffered-frame correction passed a targeted five-frame/cache-capacity regression. A subsequent complete restart and five-second live scenario passed on the final source (`20261029T163521Z`, 5.015 s, reconnect/chat 27.281 s). Seven Python boundary tests, compile checks and Perl syntax checks passed. The ten-minute run predates the framing correction; hashes distinguish them.
- Sources/portable tools/builds are in ignored `vendor/`; real credentials, SQL data, profiles, logs and raw traces in ignored `runtime/`; Python in `.venv/`. File-byte samples total about 2.57 GiB. Existing system tools and Ollama/models were preserved. M1 used no WSL/Docker, service/global PATH change, or new model.
- All six game/database/bridge listeners were verified on `127.0.0.1`. A during-trial working-set sample across the six native processes totaled 635.62 MiB; it is not a peak or inference benchmark. Project test processes are stopped at handoff.

## Boundaries and remaining limits

- M1 exposes only adjacent walkable-cell movement and ordinary printable public chat. One in-flight action, deadlines, game epochs, 128 retained request IDs, bounded nonblocking buffers, per-client tokens and finite reconnect budgets are implemented. Sending a packet is only `accepted`; matching server acknowledgment/echo is `completed`; timeout/disconnect is `unknown`. No automatic action resend exists.
- Snapshot positions can be OpenKore estimates; movement acknowledgment is not proof of arrival. Independent peer perception verifies this scenario. Durable reconciliation of uncertain actions remains M3 work.
- Stock pre-Renewal Prontera was tested; exact episode, graphical assets, combat/global routing, social behavior and long-duration operation are unverified. Unsupported modern server features disable themselves with warnings. Retry exhaustion, deliberately lost acknowledgments and output-buffer saturation were not separately fault-injected.
- The initial failed DB bootstrap directory is preserved at `runtime/mariadb/data-initialization-attempt-1`. Active data is `runtime/mariadb/data`; never reinitialize or remove it as a routine troubleshooting step.
- M0's native-Windows follow-up is tracked separately from the M1 implementation. This chat is the main coordinator and evaluator of milestone evidence and GitHub publication. The [user guide](USER_GUIDE.txt) tracks stages and starter prompts.

## Next action

When the user starts **03 - Local inference benchmark**, execute M2 using the proven native M1 runtime and existing Windows Ollama/model inventory. Recheck available RAM/VRAM and the running Ollama model-store configuration first. No M2 benchmark or model choice has been started or accepted here.
