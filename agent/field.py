"""One configured field trip. Static geometry is knowledge; actors are perception.

No global actor query, LLM movement, guaranteed loot, or uncertain-action replay.
"""
from collections import deque
import gzip
import heapq
import struct
import time

from agent.continuous import Continuous
from agent.trade import TradeLedger


TOWN, FIELD = 'prontera', 'prt_fild08'
WEAK = (1002, 1113)
DROPS = (909, 938, 512, 713)  # ordinary Jellopy, mucus, apple, bottle
PATROL = ((170, 350), (150, 330), (190, 330), (170, 310), (150, 290), (190, 290))


def distance(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))


class Geometry:
    def __init__(self, path):
        raw = gzip.decompress(path.read_bytes())
        self.width, self.height = struct.unpack('<HH', raw[:4])
        self.cells = raw[4:]
        if len(self.cells) != self.width*self.height:
            raise ValueError('Invalid static field geometry')

    def walkable(self, p):
        x, y = p
        return 0 <= x < self.width and 0 <= y < self.height and bool(self.cells[y*self.width+x] & 1)

    def path(self, start, goal, blocked=(), within=0):
        blocked = set(blocked)-{start}
        manhattan = lambda p: abs(p[0]-goal[0])+abs(p[1]-goal[1])
        queue, costs, previous = [(distance(start, goal), manhattan(start), 0, start)], {start: 0}, {}
        # Finite two-map local planner; no world route framework.
        for _ in range(50000):
            if not queue:
                break
            _, _, cost, p = heapq.heappop(queue)
            if cost != costs[p]:
                continue
            if distance(p, goal) <= within:
                route = [p]
                while route[-1] != start:
                    route.append(previous[route[-1]])
                return list(reversed(route))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (p[0]+dx, p[1]+dy)
                    if not (dx or dy) or q in blocked or not self.walkable(q):
                        continue
                    if dx and dy and not (self.walkable((p[0]+dx, p[1])) and self.walkable((p[0], p[1]+dy))):
                        continue
                    new = cost+1
                    if new < costs.get(q, 10**9):
                        costs[q], previous[q] = new, p
                        heapq.heappush(queue, (new+distance(q, goal), manhattan(q), new, q))
        raise RuntimeError('Static route unavailable or search budget exhausted')


def segment(route):
    if len(route) < 2:
        return route[0]
    direction = (route[1][0]-route[0][0], route[1][1]-route[0][1])
    end = 1
    while end < min(8, len(route)-1) and (route[end+1][0]-route[end][0], route[end+1][1]-route[end][1]) == direction:
        end += 1
    return route[end]


class FieldController(Continuous):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = self.runtime.parent/'vendor/openkore/fields'
        self.geometry = {name: Geometry(fields/(name+'.fld2.gz')) for name in (TOWN, FIELD)}
        self.field_results = deque(maxlen=8)

    def client_options(self):
        return ['--continuous', '--field']

    def snapshot_status(self):
        return super().snapshot_status() | {'mode': 'field', 'field_results': list(self.field_results)}

    def healthy(self, who):
        data = self.data(who)
        if data['hp'] <= 0:
            raise RuntimeError(who+': dead; stop for player review, no respawn action')
        return data['hp'] >= max(1, data['hp_max']*.4)

    def walk_to(self, who, x, y, within=0, transition=None):
        original = self.data(who)['map']
        if original not in self.geometry:
            raise RuntimeError('Outside configured two-map route')
        for _ in range(100):
            data = self.data(who)
            if data['hp'] <= 0:
                raise RuntimeError('Dead during navigation; no automatic respawn')
            if data['map'] != original:
                if data['map'] == transition:
                    self.note('field_portal_confirmed', who=who, source=original, destination=data['map'], snapshot=self.bridges[who].latest)
                    return
                raise RuntimeError('Unexpected portal transition')
            pos = (data['destination']['x'], data['destination']['y'])
            if distance(pos, (x, y)) <= within:
                if transition:
                    self.wait(lambda: self.data(who)['map'] == transition, 8)
                    self.note('field_portal_confirmed', who=who, source=original, destination=transition, snapshot=self.bridges[who].latest)
                return
            blocked = {(p['x'], p['y']) for p in data['players']}
            route = self.geometry[original].path(pos, (x, y), blocked, within)
            target = segment(route)
            request = self.submit(who, {'type': 'walk', 'map': original, 'x': target[0], 'y': target[1]})
            self.wait(lambda: self.results.get((who, request), {}).get('status') in ('completed', 'rejected', 'unknown'), 7)
            result = self.results[(who, request)]
            if result['status'] != 'completed':
                # A portal can invalidate the old movement before its ack.
                # Keep it unknown; the new map epoch retires authority only.
                if transition and result['status'] == 'unknown':
                    self.wait(lambda: self.data(who)['map'] == transition, 8)
                elif result['status'] == 'rejected' and result['reason'] == 'walk_blocked':
                    self.pump(1.2)
                    continue
                else:
                    raise RuntimeError('Field movement halted: '+str(result))
            # Ack is destination intent, not arrival. Allow physical movement,
            # then replan from a new snapshot (server corrections remain truth).
            self.pump(distance(pos, target)*.18+1.1)
        raise RuntimeError('Navigation segment budget exhausted')

    def outbound(self, who):
        if self.data(who)['map'] == TOWN:
            self.walk_to(who, 156, 22, transition=FIELD)
        elif self.data(who)['map'] != FIELD:
            raise RuntimeError('Cannot resume outside configured maps')
        self.walk_to(who, 170, 366, within=2 if who == 'peer' else 0)

    def home(self, who):
        returning = self.data(who)['map'] == FIELD
        if returning:
            # Stock warp center 170,378 has radius 3,2; its center is
            # unwalkable in the installed FLD. Enter at the walkable edge.
            self.walk_to(who, 170, 376, transition=TOWN)
        if self.data(who)['map'] != TOWN:
            raise RuntimeError('Return not confirmed')
        # Leave the portal, then restore the established demo gathering area.
        if returning:
            self.walk_to(who, 153 if who == 'agent' else 159, 32)
        self.walk_to(who, 154 if who == 'agent' else 153, 179 if who == 'agent' else 180)

    def eligible(self, who):
        data = self.data(who)
        if data['map'] != FIELD or not self.healthy(who):
            return []
        pos = (data['destination']['x'], data['destination']['y'])
        return sorted((m for m in data['monsters'] if m['name_id'] in WEAK and
                       130 <= m['x'] <= 215 and 280 <= m['y'] <= 375 and distance(pos, (m['x'], m['y'])) <= 14),
                      key=lambda m: distance(pos, (m['x'], m['y'])))

    def search_target(self, actors):
        for waypoint in ((170, 366), *PATROL):
            for who in actors:
                self.walk_to(who, *waypoint, within=2 if who == 'peer' else 0)
            self.pump(1.2)
            choices = self.eligible('agent')
            if len(actors) == 2:
                peer_ids = {m['id'] for m in self.eligible('peer')}
                choices = [m for m in choices if m['id'] in peer_ids]
            if choices:
                return choices[0]
        raise RuntimeError('Bounded patrol found no eligible shared visible target')

    def perceived_chat(self, who, speaker, text, since):
        return any(e['agent_id'] == who and e['kind'] == 'chat' and e['time_ms'] >= since and
                   not e['data']['self'] and e['data']['speaker'] == speaker and e['data']['text'] == text for e in self.events)

    def approach(self, who, target):
        # Four moves permit five range checks: the final move may have
        # succeeded and must be checked before declaring budget exhaustion.
        for step in range(5):
            data = self.data(who)
            visible = next((m for m in data['monsters'] if m['id'] == target and m['name_id'] in WEAK), None)
            if not visible:
                raise RuntimeError('Target no longer perceived; abandon encounter')
            pos = (data['destination']['x'], data['destination']['y'])
            if distance(pos, (visible['x'], visible['y'])) <= 1:
                return
            if step == 4:
                raise RuntimeError('Moving target approach budget exhausted')
            blocked = {(p['x'], p['y']) for p in data['players']}
            route = self.geometry[FIELD].path(pos, (visible['x'], visible['y']), blocked, within=1)
            self.walk_to(who, *segment(route))

    def field_encounter(self, cooperative):
        actors = ('agent', 'peer') if cooperative else ('agent',)
        monster = self.search_target(actors)
        target = monster['id']
        sessions = {who: self.bridges[who].session for who in actors}
        started = int(time.time()*1000)
        if cooperative:
            goal = 'Hunt '+monster['name'][:12]+' '+target+'. I lead; Bram strike; I gather.'
            self.chat('agent', goal)
            self.wait(lambda: self.perceived_chat('peer', 'M4 Alden', goal, started), 4)
            agreement = 'Agreed: strike '+target+' with Alden; Alden gathers.'
            self.chat('peer', agreement)
            self.wait(lambda: self.perceived_chat('agent', 'M4 Bram', agreement, started), 4)
            self.note('field_agreement', target=target, goal=goal, agreement=agreement, sessions=sessions)
        damage, death = {who: 0 for who in actors}, None
        deadline = time.monotonic()+60
        for turn in range(16):
            deaths = [e for e in self.events if e['agent_id'] == 'agent' and e['kind'] == 'monster_departure' and
                      e['time_ms'] >= started and e['data']['target'] == target and e['data']['dead']]
            if deaths:
                death = deaths[0]
                break
            if time.monotonic() > deadline or any(not self.healthy(who) for who in actors):
                raise RuntimeError('Combat deadline or low HP: retreat')
            who = actors[turn % len(actors)]
            if any(self.bridges[a].session != sessions[a] for a in actors):
                raise RuntimeError('Encounter epoch changed; abandon target')
            self.approach(who, target)
            # Navigation pumps observations: reconnect, HP or deadline may
            # change during approach, after the checks above.
            if any(self.bridges[a].session != sessions[a] for a in actors):
                raise RuntimeError('Encounter epoch changed during approach; abandon target')
            if time.monotonic() > deadline or any(not self.healthy(a) for a in actors):
                raise RuntimeError('Combat deadline or low HP after approach: retreat')
            # Bridge checks the current actor and melee range again.
            request = self.submit(who, {'type': 'attack', 'target': target})
            self.wait(lambda: self.results.get((who, request), {}).get('status') in ('completed', 'rejected', 'unknown'), 7)
            result = self.results[(who, request)]
            if result['status'] == 'rejected' and result['reason'] == 'target_not_visible_nearby_or_allowed':
                self.note('field_target_moved', who=who, target=target)
                self.pump(1.2)
                continue  # new perception/decision; rejected packet was never sent
            if result['status'] != 'completed':
                raise RuntimeError('Uncertain attack; do not replay: '+str(result))
            damage[who] += result['evidence']['damage']
            self.pump(1.2)
        if death is None or any(n <= 0 for n in damage.values()):
            raise RuntimeError('No confirmed kill or assigned attacker damage')
        # Stock drops reserve the first 3000 ms for the highest-damage
        # attacker. Give the agreed gatherer access to the second tier too.
        self.pump(3.2 if cooperative else 1.3)
        loot = []
        # Ordinary nearby drops only; absence is a valid result. No guarantee
        # that a ground item belongs to this kill is inferred from proximity.
        for _ in range(4):
            p = self.data('agent')['destination']
            items = [i for i in self.data('agent')['ground_items'] if i['name_id'] in DROPS and distance((p['x'], p['y']), (i['x'], i['y'])) <= 6]
            if not items:
                break
            item = items[0]
            before = self.item_count(self.data('agent'), item['name_id'])
            self.walk_to('agent', item['x'], item['y'], within=1)
            result = self.action('agent', {'type': 'take', 'target': item['id']})
            self.wait(lambda: self.item_count(self.data('agent'), item['name_id']) > before, 4)
            loot.append({'item': item, 'result': result, 'before': before, 'after': self.item_count(self.data('agent'), item['name_id'])})
        result = {'cooperative': cooperative, 'target': monster, 'goal_chosen_by': 'agent',
                  'roles': {a: 'lead_and_gather' if a == 'agent' else 'strike' for a in actors}, 'damage': damage, 'death': death, 'loot': loot}
        self.field_results.append(result)
        self.note('field_encounter_completed', result=result)
        return result

    def run(self):
        self.ready()
        self.suspended = False
        ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
        try:
            unresolved = bool(ledger.unresolved())
        finally:
            ledger.close()
        if unresolved:
            self.phase = 'recover_transfers'
            self.trade()  # inherited reconciliation only, no new offer
        try:
            # A restart may find either hunter in the field. Reconnect/login
            # establishes a fresh epoch; no prior target/action is replayed.
            for cooperative in (False, True):
                actors = ('agent', 'peer') if cooperative else ('agent',)
                self.phase = 'field_outbound'
                for who in actors:
                    if not self.healthy(who):
                        raise RuntimeError('Low HP before departure: rest in town')
                    self.outbound(who)
                self.phase = 'field_cooperative' if cooperative else 'field_solo'
                self.field_encounter(cooperative)
                self.phase = 'field_return'
                for who in actors:
                    self.home(who)
                self.cycle += 1
                self.note('field_trip_completed', cooperative=cooperative, cycle=self.cycle)
            self.phase = 'field_complete'
            self.pump(2)
        except (RuntimeError, TimeoutError, OSError, ValueError) as error:
            self.note('field_halted', error=str(error))
            # No indefinite combat/recovery. One full login can retire unknown
            # packet authority; a fresh return goal never replays the old action.
            self.phase = 'field_retreat'
            self.reconnect_clients()
            for who in ('agent', 'peer'):
                if self.data(who)['hp'] > 0:
                    self.home(who)
            raise
