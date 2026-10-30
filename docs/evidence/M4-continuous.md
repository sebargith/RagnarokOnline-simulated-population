# M4 continuous fixture runtime — Chat 06

Implemented from reviewed `a523dbfa65a08ac148ae4177bd22c9a5b98dcc23` in
`D:/Ragnarok Agents/m4-continuous`, branch `codex/m4-continuous`. Runtime commits:
`3cb8e39` (continuous controller) and `575b1d8` (startup/stale-reply repair).
The coordinator's M2 changes and unfinished M3 polish remain in their original
checkouts. This is M4 continuation. Social quality and one-hour stabilization
remain deferred; M5 was not started.

[Results, retained dialogue, source manifests and raw SHA-256 hashes](M4-continuous-results.json)
cover four continuous checks and the final-source legacy-mode checks. Raw files
remain ignored under `D:/Ragnarok Agents/runtime/evidence/`. Live logging appends
across process restarts: frozen segments can contain preceding runs; controller
records identify their run ID, game records identify client boot/session and
timestamps. The final and restart source manifests match every current source
file byte-for-byte. Documentation-only handoff edits follow those runtime commits.

## Implemented behavior

One process owns Alden, Bram and Mira. Alden alternates solo and explicitly
coordinated fixture hunts with Bram, gathers Jellopy and attempts the existing
fixed trade every three completed hunts. Mira patrols two adjacent cells.
Perceived, addressed `M4:<identity>:` public chat admits bounded dialogue in the
existing shared 9B scheduler; ordinary replies cannot create another turn.
Gameplay pumps all three bridges while inference/search is pending. Input
readiness, stale-epoch replies, finite delivery deadlines and one pending reply
per identity prevent unbounded or delayed conversations.

`scripts/live_m4.py` provides `start`, foreground `run`, `stop`, `status`,
`observe` and manual headless `say`. Ownership uses the existing shared
`m4.lock`, also checked by direct preparation and finite demos. Observation uses
status files, not another bridge consumer. Stop preserves stores and uncertain
intent; restart loads the same identities and full client inventories. No game
database initialization, account/balance reset, model download, server restart
or unrelated refactoring was used for this slice. Only project clients restart
for source loading/reconciliation; existing native services remain in place.

The old UUID cache still refuses new UUIDs after 128 in an epoch. Continuous
IDs use a boot-lifetime monotonic sequence with 128 retained results and a
high-water mark. An evicted ID is rejected forever in that boot, so rolling the
cache cannot make it executable again. Journals preserve intent before send;
old-epoch intent may be retired without claiming completion. Transfers always
remain governed by the separate durable ledger and fresh two-sided verifier.
SQL verifier results never enter an agent mind or action-selection context.

Continuous retention is explicit: four event segments of at most 1 MiB,
256 result entries, 2,048 recent events, 32 replies, 120 resource samples,
512 terminal/retired intents per identity, existing capped memory/commitments
and trade ledger, eight waiting manual commands with 30-second expiry, one
pending reply per identity with 20-second expiry. Duplicate OpenKore file logs
are disabled for continuous clients and their console output is discarded.
The shared live directory and source/status files are reused across starts;
there is no automatic accumulating run-directory history. Existing shared
server/database logs and explicitly frozen verification exports are outside
this controller's rotation policy.

Socket reconnect delays grow to 30 seconds; routine/client recovery delays
grow from 5 to 60 seconds. Each OpenKore client retains its existing finite
game reconnect budget. No game request is resent. Inference failure opens the
existing circuit; after 30 seconds and an idle scheduler, a new addressed turn
can be admitted. Old prompts are not retried. Fixed trades skip until a later
trade interval if the buyer lacks ten Zeny or the seller lacks Jellopy.

## Final-source live checks

| Run | Actual outcome |
| --- | --- |
| `d3ac8c2d253c40538091ba020f360683` | 51.938 s, 319 game events, three completed hunt/loot cycles, 30 completed actions, one delivered selected-model reply; clean stop during a durable unresolved trade |
| `590e0797b6a04495b28b2c72981b722b` | 51.812 s, 212 events, interrupted transfer reconciled as `not_applied`, no new transfer attempted, two further hunt/loot cycles, 18 completed actions, one delivered recall reply, clean stop |

The first run delivered **“M4 Mira prefers trading in the evening.”** Model
response was 13.859 s (TTFT 13.515 s; controller elapsed 13.906 s). During that
pending interval there were seven completed actions: three Alden attack
acknowledgments, a loot acknowledgment, two Mira movement acknowledgments and
the public marker-chat acknowledgment. These are server-confirmed results,
not claims made by dialogue. This is a single short sample, not a new benchmark.

A manual public message said “Remember my trail marker is ambercone. Reply
briefly.” All three separately stored it through their own public-chat
perception. It arrived while Mira's first turn was outstanding, so it did not
create another inference request. After restart, Mira answered **“You mentioned
your trail marker is an ambercone.”** Response was 1.016 s (TTFT 0.641 s).
The three persona rows were retained; before/after memory snapshots and the
public information path are in the frozen evidence. No peer memory was copied
into a prompt. Existing isolation regressions also passed.

The stop watcher observed transfer `1e59f721b2d0459e92c442113a6b1113` already
durably unknown, then issued the ordinary `stop` command. Restart reconnected
both clients and matched fresh inventories to read-only server persistence:
Alden **14 Jellopy / 170 Zeny**, Bram **7 / 30**, exactly the pre-transfer state.
The ledger became `not_applied`; recovery returned
`new_transfer_attempted: false`. The restarted controller completed only two
cycles before its second ordinary stop, so it did not reach another trade
interval. Existing tests continue to cover ambiguous, partial and stale
reconciliation and blocking across restart. No ledger entry was deleted to
bypass uncertainty.

Across those two short runs, sampled available RAM floor was **7.921 GiB** and
GPU peak **9,851 MiB**, within unchanged budgets. Sampling pauses during client
lifecycle subprocesses; these are sampled values, not continuous peaks. The
`m1` process-working-set field is zero because this runner supplies no PID set.
The live log actually rotated: a frozen segment was **1,048,072 bytes**, below
the 1,048,576-byte ceiling; the following segment was 330,087 bytes after
restart. Short samples plus retention regressions establish bounded structures,
not unattended long-duration resource stability.

## Outages, compatibility and development findings

- Development `ac20bc5b2f18462faad1a69cf4874347` completed seven cycles, 90
  completed actions, two confirmed trades and two delivered fallback replies
  with Ollama unavailable. It exercised circuit cooldown while gameplay
  continued. This predates final startup/stale-reply repairs.
- The initial startup attempt connected before client listeners existed and
  failed without game actions. Preparation now waits for each bridge listener.
  A second development run at `3cb8e39` also completed seven cycles/two trades;
  it exposed chat sent before the addressed client was ready. Final source
  suspends background sends until all three clients have passed readiness, and
  manual chat also waits for its target. The final startup-queued prompt was
  perceived and answered successfully.
- The shell inherited nonexistent `D:/Local AI/Ollama/models`; starting Ollama
  with that path exposed an empty model list and HTTP 404. Only the process
  started for this check was replaced, using the existing user-configured
  `D:/Local_AI/Models/Ollama` store. No global environment change or download.
  The 9B digest matched `77beda99ef49a70c129557ba3d6a35fc8cb829fce36cfda6f9ea60bb5221ee6f`.
- `m4-20261030T220001Z` verified the original finite trade mode on final
  source: Alden **16/170 -> 15/180**, Bram **7/30 -> 8/20**, both fresh
  inventories matching persisted rAthena state. `m4-20261030T220032Z` observed
  all three connected clients. Neither command uses the continuous runtime.
- `m4-20261030T220037Z` verified a safe web fallback: existing local SearXNG
  was unavailable, and the generated result explicitly recorded
  `SearchUnavailable` / `public search unavailable`; the fallback was actually
  delivered. Docker's Linux backend was stopped. The earlier successful
  source-attributed search remains [M4 prototype evidence](M4-prototype.md).
  One hidden startup attempt of the existing Docker Desktop installation did
  not restore its Linux engine pipe; its backend exited. No container was
  created or reconfigured. SearXNG remains unavailable at handoff; a successful
  current live web answer is not claimed.

## Commands actually run

From `D:/Ragnarok Agents/m4-continuous`, Python executable
`D:/Ragnarok Agents/.venv/Scripts/python.exe`:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -v
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m compileall -q agent bridge scripts inference
& 'D:/Ragnarok Agents/vendor/strawberry-perl/perl/bin/perl.exe' -Ibridge/lib '-ID:/Ragnarok Agents/vendor/openkore/src' '-ID:/Ragnarok Agents/vendor/openkore/src/deps' -c bridge/openkore/m1_bridge.pl
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' say --sender agent --target third --text 'Name and one preference only, very briefly?'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' say --sender agent --target third --text 'Remember my trail marker is ambercone. Reply briefly.'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' status
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' 'D:/Ragnarok Agents/runtime/evidence/watch_m4_stop.py'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/live_m4.py --runtime 'D:/Ragnarok Agents/runtime' start
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' 'D:/Ragnarok Agents/runtime/evidence/watch_m4_restart.py'
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode trade
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode observe --seconds 2
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m4.py --runtime 'D:/Ragnarok Agents/runtime' --mode web
```

The first watcher used read-only ledger inspection to issue ordinary `stop`
at the unknown-transfer boundary. The second waited for recovery, issued
`say --sender agent --target third --text 'What trail marker did I mention?'`,
then issued ordinary `stop` after two cycles and a delivered reply. The watcher
sources remain with the ignored evidence. Manual `observe --seconds 2` and
development `run --seconds 180` / `start --seconds 180` were also exercised.

**47 tests passed** after final runtime repairs. The real Perl request-window
regression admitted 1,500 requests, retained 128 results, rejected an evicted
old ID and cached a recent duplicate. Journal regression exercised 1,100
actions, bounded terminal retention and preserved an unresolved transfer;
failed sends stayed unknown. Separate regressions cover insufficient funds,
idle-only inference circuit recovery, stale replies/unready targets, and
byte-bounded rotating logs across reopen. Python compile and Perl syntax passed
(Perl reported only the environment's existing locale warning). An initial
rotation regression caught Windows CRLF byte expansion; fixed before final
source verification. Restricted-sandbox socket/Perl checks required rerunning
with normal local-process/loopback access; passing results refer to those runs.

## Limits and handoff

Use [README's continuous run path](../../README.md#continuous-three-agent-runtime-m4-continuation-chat-06).
The controller is stopped at handoff; existing native services and project
clients remain available. Start/stop restarts only client processes, retaining
identity stores and unresolved transfers. Source/status freshness and explicit
errors help diagnose unavailable services; they do not prove graphical access.

This remains the stationary Prontera Poring/guaranteed-Jellopy fixture, fixed
roles and fixed two-party offer. There is no arbitrary world routing, broader
social system, new population scale or graphical game client/assets/account.
Headless `say` speaks through a chosen existing test character. Richer dialogue
quality, longer recovery chains, shared native-service log maintenance and
one-hour/unattended stability remain unverified. Only the inference outage path
was needed here; a new forced map-server outage was not repeated. Resource
guards stop the controller on a budget violation. Stop during inference can
wait for its existing finite worker deadline; client lifecycle calls have
their own finite timeout and pause polling/sampling. Reviewer next action:
inspect these short continuous checks and use the headless run path; do not
start M5 or treat deferred social/stabilization criteria as passed.
