# M1 bridge and local operation

The tracked implementation is one OpenKore plugin, a headless output adapter, a Python stream client, native setup/lifecycle tooling, and a live acceptance harness. It has no inference, agent memory, combat controller, or social system.

## Protocol and truth

Each OpenKore process owns only its own decoded game state. The agent listens on `127.0.0.1:8765`; the temporary verification peer uses `8766`. Authenticate with a newline-delimited JSON object containing exactly `type: "auth"` and the runtime token. Tokens and game/database passwords are generated into ignored `runtime/` files. The peer exists for testing, not as another persistent agent.

After authentication the plugin emits `ready` with `resync: 1`, then a snapshot. Every event carries `v`, `agent_id`, `source`, `id`, `time_ms`, `session`, `kind`, and `data`. A session consists of a plugin boot identifier and game connection epoch. Event IDs are monotonic within a plugin process. Snapshot payloads contain connection state and, when in game, map, HP, inventory readiness/items, field dimensions, and nearby visible players. Items/players are capped at 32 each. The numeric item ID is stable; stock kRO display names can be Korean.

OpenKore maintains/interpolates positions between packets. Snapshot `position` is its client estimate; `destination` and nearby player coordinates are its current movement destination. A `movement_ack` is a server packet acknowledging a requested path, not proof that the character has arrived. The acceptance harness separately checks the other client's perception. rAthena owns authoritative movement and saved character state.

An action request contains exactly:

```json
{"v":1,"id":"unique_request_id","session":"boot:epoch","deadline_ms":1793290004000,"action":{"type":"move","map":"prontera","x":151,"y":180}}
```

Use the current snapshot's session and a fresh deadline; the example's timestamp is illustrative. The plugin rechecks the current game connection, session, map, HP, cell walkability and current destination before moving. It permits a destination at most one cell away on each axis. Chat actions contain exactly `type: "chat"` and `text`: 1–80 printable ASCII characters; leading `@`, `#`, `/` or `;` commands and control characters are rejected. No console/admin command dispatcher, model execution, SQL access, or shell command is exposed.

`action_result` carries the request ID, status and reason:

| Status | Meaning |
| --- | --- |
| `rejected` | Validation/state/rate/capacity check failed; no action packet sent. |
| `accepted` | The client sent a packet; completion is pending. |
| `completed` | A matching server movement acknowledgment or self-chat echo arrived. Evidence names the packet/destination or echoed text. |
| `unknown` | Confirmation timed out or the game disconnected while an action was pending. Never assume success or resend automatically. |

The game protocol does not carry bridge request IDs. Correlation uses one in-flight action and matching destination/text. Chat delivery to another player is confirmed separately by that player's received chat event in the test harness. A server echo alone does not establish that anyone else saw a message. Uncertain actions require reconciliation from observations before any deliberate retry; this M1 client has no retry loop. The cache does not survive an OpenKore process restart.

Repeated request IDs return their original cached status with `replay: 1`; they never execute again in the same game session. The cache retains at most 128 IDs and refuses new actions at capacity until the game epoch changes. A new game session rejects an old session ID. A Python process restart can authenticate and resync; it must retain any uncertain request ID itself if it needs to query its cached result. M3 will own durable action reconciliation.

## Bounds and recovery

- One authenticated stream and one in-flight action per plugin; one executed action per second.
- A 4,096-byte input buffer/frame limit, four parsed frames per game tick, and a 65,536-byte output buffer. Overflow closes the stream; authenticate again to receive an explicit resync snapshot. There is no replay of old observation history.
- Authentication must finish within three seconds. Action deadlines must be in the next five seconds. The Python helper requires a snapshot no older than 2.5 seconds.
- Snapshots arrive about once a second. The acceptance target is no gap over five seconds during the uninterrupted trial.
- The Python client bounds its receive buffer at 65,536 bytes and its consumer event queue at 256. Overflow raises an explicit error; callers must drain events promptly and resync after a broken connection.
- Local reconnect delays are configured as 5/10/15 seconds, without jitter. The plugin stops after three unsuccessful complete login attempts or 90 seconds without reaching the game; OpenKore also caps account-server retries at three. A fresh successful game connection resets the recovery budget. It does not resend pending actions.

## Files, shutdown and troubleshooting

`config/versions.json` pins sources, archives/checksums, protocol, character block size and build tools. `scripts/m1.py configure` generates real configs from tracked code into `runtime/openkore/`, `runtime/mariadb/` and the ignored rAthena `conf/import/` tree. This command restores the M1 fixture profile, so preserve intentional local profile edits before rerunning it. Credentials are reused on reconfiguration. Initialization refuses an existing data directory; it never clears game data.

The lifecycle registry is `runtime/processes.json`. Stop validates each recorded executable path before signaling its private hidden console; MariaDB uses authenticated `mariadb-admin shutdown`. Windows services, global PATH changes, WSL, Docker, firewall changes and Ollama are not involved. Stop retains the registry if an owned process cannot be stopped, so the failure remains visible.

Raw build/process logs live in `runtime/logs/`; client logs in `runtime/openkore/<identity>/logs/`. Acceptance results live in `runtime/evidence/<UTC-run-id>/`: `summary.json` and a trace capped at 8 MiB. Keep these out of Git: client logs can contain account/session details. Commit only reviewed sanitized evidence.

For an occupied port, inspect its owner with `Get-NetTCPConnection`; stop only a known project process. If a start fails, read its matching log before retrying. `m1.py stop` is the normal cleanup command. A stale registry or a failed initialization is not permission to delete a database: inspect it and preserve data before recovery.

Known setup findings:

- Build the solution-folder targets `server-components\login-server`, `server-components\char-server` and `server-components\map-server`. Unqualified names fail under MSBuild 16.11.
- Use `addTableFolders kRO/RagexeRE_2013_08_07a;kRO`; the generic kRO table cannot tokenize `082D` for this server.
- Use 144-byte character blocks, disable the server's optional login PIN prompt for these local fixtures, and keep game/inter-server passwords below their native 24-byte buffer size. Generated passwords are 20 ASCII bytes.
- The stock Windows console interface needs real screen/input handles. `Interface::M1Headless` writes logs, keeps the normal gameplay loop, and fails explicitly if configuration requires user input.
- Portal compilation is disabled for this adjacent-cell fixture. No global route correctness or historical episode match is established. Modern stock server features unsupported by protocol `20130807` report warnings and disable themselves.
