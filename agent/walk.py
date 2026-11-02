"""Walk reachability inside maps, shared by the field options and the zone table build.

A zone is a connected set of walkable cells of OpenKore's field file (.fld2). OpenKore's
route only steps diagonally when both orthogonal cells are walkable, so 4-neighbour
connectivity gives the same zones as its 8-direction search. Portals join zones:
map-to-map portals and same-map walk portals (castle inner doors) alike.
config/walk-zones.json (scripts/build_walk_zones.py) lists every free, talk-less
portal with the zone it is entered from and the zone it lands in, plus anchor cells
per map; M1Travel::plan reads the same table.
"""
from collections import deque
from functools import lru_cache
import gzip
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ROOT.parent/'vendor/openkore/fields'
ZONES = ROOT/'config/walk-zones.json'
MAX_HOPS = 3    # M1Travel::MAX_HOPS: map-to-map hops.
MAX_INNER = 4   # M1Travel::MAX_INNER: same-map portals in one trip.
APPROACH = 2    # M1Travel::APPROACH


@lru_cache(maxsize=4)
def grid(name, fields=None):
    """(width, height, cells) of OpenKore's .fld2; bit 1 = walkable. None if missing."""
    path = Path(fields or FIELDS)/f'{name}.fld2.gz'
    if not path.exists():
        return None
    data = gzip.decompress(path.read_bytes())
    width, height = struct.unpack('<HH', data[:4])
    return width, height, data[4:]


def walkable(g, x, y):
    width, height, cells = g
    return 0 <= x < width and 0 <= y < height and cells[y*width + x] & 1


def approach(g, x, y):
    """Nearest walkable cell within APPROACH, same order as M1Travel::approach_cell."""
    cells = [(x+dx, y+dy) for dx in range(-APPROACH, APPROACH+1) for dy in range(-APPROACH, APPROACH+1)
             if x+dx >= 0 and y+dy >= 0 and walkable(g, x+dx, y+dy)]
    return min(cells, key=lambda c: (max(abs(c[0]-x), abs(c[1]-y)), abs(c[0]-x) + abs(c[1]-y), c[1], c[0]),
               default=None)


def flood(g, start, stop=None):
    """4-neighbour walkable cells from start. With stop(cell) -> value, returns the first
    value found (None when the whole component has none); otherwise the set of cells."""
    width, height, cells = g
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        if stop:
            hit = stop((x, y))
            if hit is not None:
                return hit
        for c in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if c not in seen and 0 <= c[0] < width and 0 <= c[1] < height and cells[c[1]*width + c[0]] & 1:
                seen.add(c)
                queue.append(c)
    return None if stop else seen


ISOLATED = 0    # Zone of a cell whose component has no portal; zones count from 1.


def load(path=None):
    table = json.loads(Path(path or ZONES).read_text(encoding='utf-8'))
    edges = {}
    for m, x, y, to, tx, ty, zf, zt in table['portals']:
        edges.setdefault((m, zf), []).append((x, y, to, tx, ty, zt))
    anchors = {m: {(x, y): z for x, y, z in cells} for m, cells in table['anchors'].items()}
    return {'edges': {k: sorted(v, key=lambda e: (e[2], e[5], e[0], e[1])) for k, v in edges.items()},
            'anchors': anchors}


def from_graph(graph):
    """Walk table for a map-level graph {map: [[x, y, to, tx, ty], ...]}: one zone per map
    and no field files (tests and maps without walk data)."""
    edges = {}
    for m, rows in graph.items():
        for x, y, to, tx, ty in rows:
            edges.setdefault((m, 1), []).append((x, y, to, tx, ty, 1))
    return {'edges': {k: sorted(v, key=lambda e: (e[2], e[5], e[0], e[1])) for k, v in edges.items()}, 'anchors': {}}


_ZONE_CACHE = {}


def zone_at(walk, name, cell, fields=None):
    """Zone of the cell (or the nearest walkable one within APPROACH); ISOLATED when no
    walkable cell is near or its component holds no portal; None (any zone) only for a
    map without walk data. Bounded cache."""
    key = (id(walk['anchors']), name, tuple(cell))
    if key not in _ZONE_CACHE:
        g, anchors = grid(name, fields), walk['anchors'].get(name)
        if not g or anchors is None:
            _ZONE_CACHE[key] = None
        else:
            start = approach(g, *cell)
            _ZONE_CACHE[key] = (flood(g, start, anchors.get) if start else None) or ISOLATED
        if len(_ZONE_CACHE) > 256:
            _ZONE_CACHE.pop(next(iter(_ZONE_CACHE)))
    return _ZONE_CACHE[key]


def zones_of(walk, name):
    return sorted({z for m, z in walk['edges'] if m == name})


def route(walk, start, goal, start_zone=None, goal_zone=None):
    """Fewest map hops then fewest inner doors from (start, zone) to (goal, zone), as
    M1Travel::plan. A None zone means any zone of that map. Returns
    {'hops', 'inner', 'via', 'nodes'} or None. via is the last other map before goal."""
    starts = [(start, z) for z in ([start_zone] if start_zone is not None else zones_of(walk, start))]
    if not starts:
        return None
    goal_ok = lambda n: n[0] == goal and (goal_zone is None or n[1] == goal_zone)
    cost = {n: (0, 0) for n in starts}
    prev = {n: None for n in starts}
    buckets = {0: list(starts)}
    for level in range((MAX_HOPS + 1) * (MAX_INNER + 1)):
        for node in buckets.get(level, []):
            if cost[node][0] * (MAX_INNER + 1) + cost[node][1] != level:
                continue  # Reached again later more cheaply.
            if goal_ok(node):
                nodes = [node]
                while prev[nodes[0]]:
                    nodes.insert(0, prev[nodes[0]])
                via = next((n[0] for n in reversed(nodes) if n[0] != goal), None)
                return {'hops': cost[node][0], 'inner': cost[node][1], 'via': via, 'nodes': nodes}
            hops, inner = cost[node]
            for x, y, to, tx, ty, zt in walk['edges'].get(node, []):
                step = (hops, inner + 1) if to == node[0] else (hops + 1, inner)
                nxt = (to, zt)
                if (nxt in cost and cost[nxt] <= step) or step[0] > MAX_HOPS or step[1] > MAX_INNER:
                    continue
                cost[nxt], prev[nxt] = step, node
                buckets.setdefault(step[0] * (MAX_INNER + 1) + step[1], []).append(nxt)
    return None
