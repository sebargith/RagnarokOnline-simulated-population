"""Ask the selected local 9B model a question with one optional web search."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inference.web_turn import run_web_turn  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Public-information question for the selected 9B model")
    args = parser.parse_args()
    operating = json.loads((ROOT / "config/m2-operating.json").read_text(encoding="utf-8"))
    web_config = json.loads((ROOT / "config/web-search.json").read_text(encoding="utf-8"))
    result = run_web_turn(args.question, operating, web_config)
    print(result["answer"])
    if result["search"]:
        print("\nWeb search sources (external, unverified):")
        for item in result["search"]["results"]:
            print(f"- {item['title']}: {item['url']}")


if __name__ == "__main__":
    main()
