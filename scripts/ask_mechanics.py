"""Ask the local chat model about a public classic RO mechanics category."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inference.mechanics import mechanics_lookup
from inference.roles import role_operating

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('question')
args = parser.parse_args()
# Questions may come from players, so they stay on the local chat role.
operating = role_operating('chat')
web = json.loads((ROOT / 'config/web-search.json').read_text(encoding='utf-8'))
print(json.dumps(mechanics_lookup(args.question, operating, web), ensure_ascii=False, indent=2))
