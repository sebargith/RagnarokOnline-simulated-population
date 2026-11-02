# P5 — reachability on foot inside each map

Date: 2026-11-01, Claude. Branch `codex/single-agent-plan`; code `e574b18`, `80c13c2`, `38034e7`.

## Failure

- The run `runtime/p5/evidence/resume-20261101-unique-1/` got stuck about 5 minutes in.
- A periodic field review led Groq to choose `prt_fild01`.
- `travel` c_384 planned prontera → `prt_castle` (156,360) → `prt_gld` (102,181) → `prt_fild01` (159,298) → (49,331).
- It crossed into `prt_castle` and stopped at (102,20) with `failed/unreachable` (event 2074).
- **Cause:** `M1Travel::walk_graph`/`plan` and the field options only checked that portals exist.
- Inside the castle, (102,181) cannot be reached on foot from (102,20). You only get there through two inner doors: (102,73)→(102,88) and (102,129)→(102,140).

## Change

- **Walk zones** (`agent/walk.py`):
  - connected sets of walkable cells in OpenKore's `.fld2`, with 4 neighbours;
  - OpenKore's route only steps diagonally if both orthogonal cells are walkable, so the zones are the same as with its 8-direction search.
- **Generated table** `config/walk-zones.json`, from `scripts/build_walk_zones.py`:
  - it reads `tables/portals.txt` as `FileParsers::parsePortals` does, with the filter of `walk_graph` (free, no dialogue, no dynamic group), and also keeps portals within the same map;
  - each portal stores the zone it is entered from (the walkable cell within 2) and the zone it lands in, plus anchor cells per map;
  - 2878 portals in 485 maps, from pinned OpenKore `e0b04ee`;
  - to build it: `python scripts/build_walk_zones.py` (about 16 s), then `python scripts/build_p5_hunting.py`.
- **Planner** `M1Travel::route` (`plan` wraps it):
  - searches (map, zone) nodes: fewest map hops (≤3), then fewest inner doors (≤4);
  - starting zone: from the observed cell, walking to the first anchor, with a cache of 64 cells;
  - destination zone: loads that map's `Field`, with a cache of 4 maps;
  - an inner door is a leg confirmed only by the server's map-change packet; `map_changed` now listens to it for a `travel` on that leg;
  - with no path: `rejected/no_walk_route`, with `walk` set to `start_isolated`, `destination_unreachable` or `no_zone_path`, without moving;
  - if the table is missing: `walk_zones_missing`.
- **Fields and supply** (`agent/hunting.py`, `agent/tutorial.py`):
  - a field option needs an entry spot reachable from the character's real zone;
  - it also needs a route from that zone to the Prontera shop (104,51) and back;
  - the tutorial towns use the landing and save zones;
  - each `p5-fields.json` entry now carries its zone, and the entry spots did not change.
- **Conciliation** (`reconcile-travel`, `SoloCycle.reconcile_failed_travel`):
  - it retires the blocked `travel` only with its single `failed` final result in the history;
  - it needs two fresh snapshots from one session (the bridge without a pending action), with the character still on the map where it stopped;
  - the original result is kept, the failure counts, and nothing is resent.
  - It also covers `unknown/unexpected_warp`, but only if there is no Zeny change and no map change and the character is still on the cell where the bridge stopped it. That case does not count as a failure (`retired_same_map_warp`).

## Checks

- `tests/test_p5_walk_zones.py` (8, real data, Perl and Python):
  - (102,20) and (102,181) are in different zones; with no inner doors, `prt_gld` is unreachable;
  - with the doors, the legs are (102,73) → (102,129) → (102,181) → `prt_gld`;
  - c_384 (prontera → `prt_fild01` 49,331) now avoids the castle;
  - the routes `prt_fild08`↔Prontera, `prt_fild06`, `prt_fild05` and Izlude still hold;
  - an isolated cell is rejected with its reason;
  - the Perl graph equals the table, and Python and Perl agree;
  - options from the castle are reachable both ways;
  - the regeneration is identical.
- `tests/test_p5_walk_zones.py` also covers (11 in total):
  - the castle door hop with the server landing (102,91);
  - the time budget for the route;
  - `navigate` inside the map.
- `tests/test_p2_cycle.py`: conciliation of a failed travel and of a same-map warp (rejections and acceptance).
- `python -m unittest discover -s tests`: 253 OK. `perl -c bridge/openkore/m1_bridge.pl`: OK.

## Live run (Nilo, account 2000031)

- **Before:**
  - checkpoint `blocked` `travel:failed/unreachable`, phase `return`, 136 kills, c_384 in `inflight`;
  - Nilo stationary in `prt_castle` (102,20);
  - free RAM 7.81 GiB, GPU 2180/16384 MiB;
  - rAthena, MariaDB, Ollama and client 31704 on 8771; no runner active.
- **Conciliation:**
  - the first attempt was rejected without changes because it required a new session; the bridge resumes the same one (`resync`);
  - after `38034e7`: `retired_failed_travel`, `active`/`return`, failures 1, no `inflight`.
- **Client:** 31704 was still running the bridge loaded at 11:00, with the old planner. With the user's approval, it was stopped while idle with `prepare_p5.py stop`, and the run started a new one.
- **Command:** `python scripts/run_p5_background.py --runtime ../runtime --summary ../runtime/p5/evidence/walk-reachability-1/summary.json --seconds 900 --max-actions 150`.

- **Attempt 1:** the runner tried to connect before the new client was accepting connections (`ConnectionRefused`) and exited after 8 s, without acting.
  - Likely cause: `Listen => 1` in the bridge plus the `wait_port` probe.
  - The client was left running and the run was repeated with `--reuse-client`.
- **Attempt 2 (10 s):**
  - c_1 planned the route through the inner doors, (102,73) → (102,129) → (102,181) → `prt_gld` → `prt_fild01`;
  - at the first door the server landed at (102,91), giving `unknown/unexpected_warp`;
  - fixed in `eda1a07`, conciliated as `retired_same_map_warp`, and the client was restarted again (approved).
- **Attempt 3 (≈300 s):**
  - c_1 `completed/arrived` in 136 s: hops prt_castle → prt_castle (102,143) → `prt_gld` → `prt_fild01`.
  - Field review (`periodic_review`): every option was reachable (prt_fild06, prt_fild01, prt_fild05, prt_fild00, prt_fild04). Groq chose prt_fild00.
  - c_4 `prt_fild01` → `mjolnir_09` → `prt_fild00` made both hops, but ran out of the fixed 150 s on the last leg, giving `failed/timeout`.
  - Fixed in `fae125e` and conciliated (`retired_failed_travel`).
- **Attempt 4 (870 s, exit 0 by `time_budget`, 52 actions, 1 inference):**
  - `navigate` to (28,136) in prt_fild00 with a 77 s budget: arrived.
  - Field review: options prt_fild01, prt_fild05, prt_fild00 and prt_fild04, all reachable. Groq kept prt_fild00.
  - Kills 136 → 148, 13 pickups, 2 sales.
  - Two complete supply round trips (3 hops each way, via mjolnir_09 and prt_fild05), all `arrived`, in 213–225 s against a 300 s budget.
  - No `unknown`, `failed`, deaths or retreats.
  - At the end, travel c_56 back to prt_fild00 (300 s) was still in flight, with the checkpoint `active`. The next run should pick up its retained result without resending it.
- **Local evidence, outside Git:** `runtime/p5/evidence/walk-reachability-1/`, with summaries and logs for every attempt, `state-*` at each step, and `events-live.json`.

## Limits

- The zones come from OpenKore's `.fld2` and `portals.txt`. A wall or portal on the server that differs from those files is still discovered while walking, as `failed/unreachable` or `portal_not_taken`.
- Exploration moves to cells in the current map with `navigate`, without checking zones. A cell in another zone fails with the usual result, so it does not block the cycle.
- The tutorial towns use the save point as an approximation of where the character is in town.
- The landings in OpenKore's table can differ from the server's. For map-to-map portals the hop only checks the map; for inner doors, the zone.
- The time budget is capped at 300 s. A trip of more than about 620 straight-line cells could still run out.
- Field options do not weigh the length of the supply trip. prt_fild00 costs about 7.5 minutes per round trip to Prontera, which eats much of the hunting time.
- Attempt 1 showed a start-up race between `prepare_p5.start` and the runner. It was worked around by reusing the client, and not fixed.
