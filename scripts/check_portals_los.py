"""R1: compare OpenKore's tables/portalsLOS.txt (walk reachability between portals
of the same map, used by CalcMapRoute) with our config/walk-zones.json (same
zone = reachable on foot). Read-only; prints agreement and every disagreement."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOS = ROOT.parent/'vendor/openkore/tables/portalsLOS.txt'


def load_los(path=LOS):
    """(source, target) -> walk distance; 0 means not reachable."""
    out = {}
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        t = line.split()
        if line.startswith('#') or len(t) < 7:
            continue
        src = (t[0], int(t[1]), int(t[2]))
        for i in range(3, len(t) - 3, 4):
            out[(src, (t[i], int(t[i + 1]), int(t[i + 2])))] = int(t[i + 3])
    return out


def load_zones(path=ROOT/'config/walk-zones.json'):
    zone = {}
    for m, x, y, dest, dx, dy, src_zone, dest_zone in json.loads(Path(path).read_text())['portals']:
        zone[(m, x, y)] = src_zone
        zone.setdefault((dest, dx, dy), dest_zone)
    return zone


def compare(los, zone):
    counts, diff = collections.Counter(), []
    for (a, b), dist in sorted(los.items()):
        if a[0] != b[0] or a == b or a not in zone or b not in zone:
            counts['skipped'] += 1
            continue
        same = zone[a] == zone[b]
        counts['agree' if same == (dist > 0) else 'disagree'] += 1
        if same != (dist > 0):
            diff.append({'from': a, 'to': b, 'los_dist': dist, 'zones': [zone[a], zone[b]]})
    return counts, diff


def main():
    los, zone = load_los(), load_zones()
    counts, diff = compare(los, zone)
    castle = sorted(b[1:] + (d,) for (a, b), d in los.items() if a == ('prt_castle', 102, 16) and d > 0)
    print(json.dumps({'counts': counts, 'prt_castle_entrance_reachable': castle,
                      'prt_castle_entrance_to_prt_gld_exit': los.get((('prt_castle', 102, 16), ('prt_castle', 102, 181))),
                      'disagreements_by_map': collections.Counter(d['from'][0] for d in diff),
                      'disagreements': diff}, indent=1))


if __name__ == '__main__':
    main()
