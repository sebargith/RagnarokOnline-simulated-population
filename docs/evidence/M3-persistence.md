# M3 persistent agent: implementation and duration evidence

Current outcome: frozen code `beb18a7` completed the 30-minute movement,
dialogue, commitment/restart and reconnection scenario. The subsequent search
repair passed a targeted live check; human quality acceptance remains pending. See
[numeric evidence and hashes](M3-results.json) and [all seven replies](M3-conversations.md).
The sections below retain the actual development sequence, including failures.

## Initial persistence foundation (9917397)

`agent/memory.py` stores immutable persona bindings and distinct observations,
reported claims, generated dialogue, action records, and commitments. Each write
commits immediately. Duplicate keys are ignored per identity. Retention is 512
ordinary records plus 16 commitments per identity. Retrieval is at most 16 records
(8 by default) and 2,400 serialized data characters. Commitments are retrieved
first. Record payloads are limited to 4,096 serialized characters.

Executed in the clean `m3-worktree` checkout using the existing Python 3.11 venv:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -p test_m3_memory.py -v
```

Both tests passed. They verify close/reopen continuity, persona mismatch
rejection, identity isolation, retained unknown action status, commitment
provenance, duplicate suppression and retention after 530 ordinary writes.
These checks do not establish actual server-action reconciliation, model
grounding, responsiveness, social quality or 30-minute continuity.

The initial next step, subsequently implemented, was to connect a controller preserving uncertain
requests and per-game-epoch bridge capacity across orchestrator restarts. Then
add a bounded background dialogue worker and controller-owned public search
queries before building the live acceptance harness. No M4 work is authorized.

## Deterministic controller slice

`agent/routine.py` now connects durable intent/capacity tracking to the existing
M1 bridge. It saves a unique request ID before sending, never automatically
replays an uncertain request, retains accepted/completed/rejected/unknown as
distinct outcomes, and rejects stale snapshots. Unknown outcomes block further
routine actions in the same epoch; a new observed epoch records uncertainty
before resetting capacity. This conservative same-epoch stop needs explicit
reconciliation in the later orchestration slice. Capacity is 110 reserved
actions per game epoch, retained across Python restarts, below M1's 128-entry
cache. The routine only requests adjacent movement every 20 seconds.

The final full suite passed: **31 tests in 3.790 seconds**, including send
failure preserving unknown status and capacity after restart. Compileall and
`git diff --check` passed. The initial broader-suite stall was reproduced with a five-second faulthandler
watchdog: Windows Python `socket.socketpair()` blocked in `socket.py:294 accept`
inside the sandbox. Outside the sandbox all seven existing bridge tests passed,
then the full 30-test suite passed in 3.946 seconds. This preceded the added
send-failure regression; the final suite count is recorded at the next commit.

Live M1 bridge listeners were absent because both registered OpenKore clients
had exited. Only those project clients were restarted using `scripts/m1.py`;
the database/server were left running. An initial routine stopped after one
acknowledgment because OpenKore's path-origin `position` differed from its
acknowledged `destination`. The corrected controller uses destination for
adjacent target selection and relies on the plugin's current-state recheck.

Corrected live command, executed from this worktree:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/run_m3.py --runtime 'D:/Ragnarok Agents/runtime' --seconds 45
```

Result: 45.094 seconds, 53 events, two accepted actions followed by matching
`0087` movement acknowledgments to (150,180) and (151,180), no pending action at
exit. Raw bounded output: `runtime/evidence/m3-routine/live.txt` in the original
workspace. This is a short movement proof, not the 30-minute M3 scenario or
independent arrival verification. No inference/search has entered this slice.

A subsequent 25.031-second Python restart run received 30 events and one
accepted/completed movement acknowledgment to (150,180). The persisted epoch
counter increased from 3 to 4 and direction continued from -1 to +1, without
replaying earlier requests. Raw output: `runtime/evidence/m3-routine/restart.txt`.
Both live runs ended with no pending action. The fake-bridge regression, rather
than this live run, covers a restart with an unresolved accepted action.

## Dialogue and recovery integration

The next slice adds `agent/dialogue.py`, the `--dialogue` runner mode and
`scripts/accept_m3.py`. One identity has one outstanding background turn and
one bounded unsent reply; player test chat must start with `M3:`. Admission is
at most once per ten seconds. Model JSON permits only an 80-character printable
chat response, with command prefixes denied. The selected M2 streaming service
retains its 2,048 context/160 output token limits, finite deadlines, single
worker and zero retries. Gameplay polling never waits for inference or search.

Retrieval filters record categories before applying the record/character cap.
Commitment questions retrieve commitments; map questions retrieve observations;
web answers receive only a single external snippet and no private records.
Search supports only `M3: web poring`: one controller-owned literal query,
`Ragnarok Online classic Poring monster`. The worker receives neither player
chat nor memory. Replies name the supplied source hostname; retained dialogue
records include its exact URL. This is intentionally not arbitrary web search.

A commitment request records an intention. The deterministic acknowledgment
becomes a spoken commitment only after its matching server chat echo. Unknown
movement can resume toward a new goal after its deadline, a quiet interval and
two stable fresh destination observations, without marking the old action
completed or replaying it. Unknown chat is abandoned without retransmission.
The runner uses an OS file lock and a three-attempt stream reconnect budget.

Development preflights retained under the original workspace's ignored
`runtime/evidence/`:

- `m3-20261030T003326Z`: found unrelated commitment context contaminating map
  and web answers. This is a failed grounding preflight, not acceptance.
- `m3-20261030T003549Z`: narrowed retrieval produced grounded restart recall
  and a Poring web answer, but some replies were dropped during pending-action
  reconciliation. A one-reply outbox and shared send spacing address delivery.
- `m3-20261030T003834Z`: explicit refused inference endpoint before restart and
  refused search endpoint after restart produced fallback dialogue; movement
  acknowledgments continued. Post-restart maximum snapshot gap was 1.032 s,
  zero disconnected snapshots. The scripted fault endpoints affect only these
  child processes, not global Ollama/SearXNG settings. One map reply was dropped
  while the bounded outbox was occupied; it remains a development limitation.

All **36 automated tests passed in 3.794 s**, outside the sandbox, and compile
checks passed. Tests include pending/failed inference with continuing routine
actions, invalid output, stale dialogue, private-query exclusion, same-epoch
movement reconciliation and unknown outcomes across restart. Installed Ollama
0.40.12 and the selected 9B digest were rechecked against operating config.

## Frozen duration attempt: resource gate blocked

Frozen implementation: `beb18a7`. Command actually executed:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/accept_m3.py --runtime 'D:/Ragnarok Agents/runtime' --seconds 1800 --reconnect
```

Run `m3-20261030T004247Z` stopped at its initial resource sample after **0.110 s**.
Available physical RAM was **1.736 GiB**, below the unchanged **2 GiB** M2 floor;
GPU memory was **9,849 MiB**, below 14,336 MiB. No chat, routine movement,
orchestrator restart or map-server restart occurred in this attempt. The child
was stopped by the harness. Raw `summary.json`, `resources.json`, source hashes
and the empty child log remain in that ignored evidence directory.

Three subsequent RAM samples were **1.677 / 1.692 / 1.645 GiB**. This is a
persistent current-environment shortage, not a measured 30-minute agent result.
The resource floor was not relaxed and unrelated applications were not closed.
The user was asked to free memory or defer the trial. The database, server and
both test clients remain running; no M1 data/configuration was reinitialized.

At that failed attempt, the duration/reconnect and budget checks were pending.
The next step was to regain at least 2 GiB RAM and retry; the successful retry
is recorded below. The
scenario records source hashes, peer observations and five-second RAM/GPU
samples; these are sampled peaks, not continuous hardware maxima.

## Successful duration run and final review

After available RAM recovered to **7.727 GiB**, the exact same command was
retried on unchanged implementation `beb18a7`. Run **m3-20261030T004509Z**
completed **1800.657 seconds** and exited zero. All manifest source hashes still
match. The earlier RAM gate did not recur; no resource limit was changed.

| Check | Observed result |
| --- | --- |
| Movement | 88 matching server path acknowledgments; peer independently saw both (150,179) and (151,179) |
| Chat | Seven server echoes and seven corresponding peer-received replies |
| Action outcomes | 95 accepted, 95 completed; no rejected/unknown results in this run |
| Orchestrator restart | Once at halfway; memory retained identity, spoken commitment and observed map |
| Game reconnection | Map server restarted once; 25 disconnected snapshots, then epoch 2 and resumed movement |
| Snapshot gaps | Maximum 1.033 s before / 1.031 s after orchestrator restart |
| Resources | 356 samples; minimum available RAM 6.235 GiB; GPU sampled peak 10,341 MiB |
| No-search warm turns | n=3; nearest-rank p95 TTFT 0.609 s, service/response 0.891 s, queue zero |
| No-search cold-budget turns | n=2; maximum TTFT 9.812 s, service/response 10.344 s |
| Web-assisted turn | n=1; total 2.890 s, model service 0.875 s; reported separately |

All measured latency/resource values meet the existing M2 numeric targets.
The small live sample is not another repeated capacity benchmark. `cold`
denotes the first-turn budget in each orchestrator instance, not a proven
fresh Ollama process. No model download or global runtime setting changed.

The agent declined to treat the Aden rumor as observation and admitted it did
not know the peer's password. Its promise was spoken before restart and
retrieved afterward; the observed map was also recalled. The full peer-received
conversation is retained without editing in the linked review document.

The web query contained only `Ragnarok Online classic Poring monster`. However,
selecting the last result supplied a snippet for **Ragnarok M: Eternal Love and
Classic**, and the agent replied with an unhelpful attributed refusal. It did
not promote the snippet to game truth or fabricate an answer, but **useful
classic-PC search integration is not accepted**. Search relevance and the
external-claim answer policy require a focused repair and targeted evidence.

The complete suite passed again after the duration run: **36 tests in 3.786 s**.
Compile checks, local Markdown-link checks and whitespace checks passed.
No deliberately lost game acknowledgment, reconnect-budget exhaustion or
output-buffer saturation was live-injected; unit checks and the separate short
outage run cover the narrower boundaries recorded above. Human continuity,
naturalness and social-quality acceptance remain open. No M4 was started.

The report was generated with this executed command:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/report_m3.py 'D:/Ragnarok Agents/runtime/evidence/m3-20261030T004509Z' --web-run 'D:/Ragnarok Agents/runtime/evidence/m3-web-20261030T012548Z'
```

Raw traces, SQLite state, resource samples and source hashes remain in that
ignored run directory. The tracked report contains sanitized fixture dialogue,
metrics and hashes. Initial implementation commits: `9917397`, `696f690`, `beb18a7`.

## Targeted search repair (7d875e5)

The repair excludes snippets identifying Ragnarok M/Eternal Love/mobile,
selects one candidate identifying PC Ragnarok Online or pre-Renewal, and
explicitly permits summarizing a source's claim without treating it as a game
observation. Exact URLs remain in the retained external record. If attribution
and generated text exceed the bridge's 80-character limit, chat displays a
word-boundary excerpt with `...`; the complete generated sentence is retained
separately. This addresses source relevance and an unhelpful overflow fallback.
It is a narrow heuristic, not a general search-quality guarantee.

The first repair check, `m3-web-20261030T012412Z`, selected the correct PC source
but exposed the old overflow fallback. The final repair check used:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/check_m3_web.py --runtime 'D:/Ragnarok Agents/runtime'
```

Run **m3-web-20261030T012548Z** completed **35.406 s**. The peer received exactly
one source-attributed reply: `Web (ratemyserver.net): Source lists stats, drops,
and spawn info for...`. The selected source was the PC/pre-Renewal Poring page
at `https://ratemyserver.net/index.php?page=mob_db&mob_id=1002`; its snippet
explicitly lists spawn, drop and stats information. The full generated sentence
and exact snippet are retained in [results](M3-results.json).

The web-assisted turn took **2.532 s** overall, model service **0.922 s**, TTFT
**0.437 s**. One routine movement received accepted/completed acknowledgments
during the same check; 44 events, maximum snapshot gap **1.031 s**, no
disconnected snapshot, no pending action at exit. The complete **37-test suite
passed in 3.886 s** after the final excerpt change; compile and artifact/link
checks also passed. Source hashes are in the targeted run's `summary.json`.

The duration trial remains evidence for `beb18a7`; no additional 30-minute run
is claimed for `7d875e5`. Only dialogue/source selection and its targeted
checker changed; controller, persistence and recovery sources are identical.
Operation beyond the demonstrated duration is unverified; the controller
deliberately stops at 110 reserved actions per game epoch to respect M1's
finite request cache. General search, combat, routing and transfer reconciliation
remain outside M3's demonstrated slice.

Next: user/coordinator review of all seven duration replies plus the repaired
search reply for continuity and naturalness. M3 remains awaiting that human
acceptance. Do not start M4 or claim human approval.
