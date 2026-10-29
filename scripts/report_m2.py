"""Export compact M2 results and a deterministic review set; never approve quality."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bench_m2 import summarize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(manifest, summary, rows):
    limits = manifest["limits"]
    checks = {}
    expected = {(i, n, t, r, s, c) for i in (0, 1) for n in limits["profiles"]
                for t in ("cold", "warm") for r in range(limits["repeats"]) for s in range(n)
                for c in ("conversation-1", "conversation-2", "recall", "action-valid", "action-injection")}
    actual = {(r["model_index"], r["sessions"], r["profile"], r["repeat"], r["session"], r["case"]) for r in rows}
    checks["complete_matrix"] = (manifest["args"]["repeats"] == limits["repeats"] and
                                 manifest["args"]["profiles"] == limits["profiles"] and
                                 manifest["args"]["models"] == [0, 1] and len(rows) == len(expected) and actual == expected)
    checks["runtime_completed"] = summary["fatal"] is None
    checks["monitor"] = len(summary["monitor_errors"]) <= limits["max_monitor_errors"]
    checks["resource_guard"] = not summary["resource_guard_tripped"]
    checks["available_ram"] = summary["resources"]["min_available_ram_gib"] >= limits["min_available_ram_gib"]
    checks["gpu_peak"] = summary["resources"]["peak_gpu_used_mib"] <= limits["max_gpu_used_mib"]
    checks["m1"] = all(s["snapshots"] > 0 and s["disconnected"] <= limits["max_m1_disconnected_snapshots"] and
                       s["max_gap_s"] <= limits["max_m1_snapshot_gap_s"] for s in summary["m1"].values())
    models = []
    for index in (0, 1):
        selected = [r for r in rows if r["model_index"] == index]
        aggregate = summarize(selected)
        own = {"transport": aggregate["failures"] <= limits["max_transport_failures"],
               "truncation": aggregate["truncations"] <= limits["max_truncations"],
               "foreign_markers": aggregate["leaks"] <= limits["max_foreign_markers"]}
        cases = {}
        for case, threshold in (("recall", "min_recall_exact_fraction"),
                                ("action-valid", "min_valid_action_fraction"),
                                ("action-injection", "min_injection_none_fraction")):
            subset = [r for r in selected if r["case"] == case]
            passed = sum(r.get("score", {}).get("pass") is True for r in subset)
            cases[case] = {"n": len(subset), "passed": passed, "fraction": passed/len(subset) if subset else 0}
            own[case] = bool(subset) and cases[case]["fraction"] >= limits[threshold]
        for sessions in limits["profiles"]:
            for profile in ("cold", "warm"):
                subset = [r for r in selected if r["sessions"] == sessions and r["profile"] == profile]
                group = summarize(subset)
                if not subset or group["failures"]:
                    own[f"{sessions}/{profile}/latency"] = False
                    continue
                if profile == "warm":
                    for metric in ("ttft_s", "service_s", "queue_s", "response_s"):
                        own[f"{sessions}/warm/{metric}"] = group[metric]["p95"] <= limits["warm_p95_"+metric]
                else:
                    first = [r for r in subset if r["cold_request"]]
                    own[f"{sessions}/cold/first_ttft"] = bool(first) and max(r["ttft_s"] for r in first) <= limits["cold_first_max_ttft_s"]
                    own[f"{sessions}/cold/response"] = group["response_s"]["max"] <= limits["cold_profile_max_response_s"]
        models.append({"index": index, "name": manifest["config"]["models"][index]["name"],
                       "automatic_pass": all(checks.values()) and all(own.values()),
                       "checks": own, "cases": cases, "aggregate": aggregate})
    return {"shared_checks": checks, "models": models, "human_review": "pending", "milestone_accepted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--development-runs", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    run = args.run.resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    for path, expected in manifest["source_hashes"].items():
        if sha(ROOT/path) != expected:
            raise RuntimeError(f"source changed since run: {path}; restore the recorded bytes before reporting")
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
    acceptance = evaluate(manifest, summary, rows)
    qualified = [m["index"] for m in acceptance["models"] if m["automatic_pass"]]
    acceptance["technical_selected_index"] = min(qualified) if qualified else None
    priming = json.loads((run / "priming.json").read_text(encoding="utf-8"))
    public = {"run": run.name, "raw_directory": str(run), "source_commit": manifest["source_commit"],
              "source_hashes": manifest["source_hashes"], "runtime_version": manifest["version"],
              "python": manifest["python"], "config": manifest["config"], "limits": manifest["limits"],
              "raw_sha256": {file: sha(run/file) for file in ("manifest.json", "requests.jsonl", "resources.jsonl", "summary.json", "priming.json")},
              "artifacts": [{"tag": m["tag"], "details": m["show"]["details"],
                             "thinking": m["show"].get("thinking"), "parameters": m["show"].get("parameters"),
                             "template_sha256": hashlib.sha256(m["show"].get("template", "").encode()).hexdigest()}
                            for m in manifest["models"]],
              "summary": summary, "acceptance": acceptance,
              "priming_usage": {"n": len(priming), "input_tokens": sum(p["prompt_eval_count"] for p in priming),
                                "output_tokens": sum(p["eval_count"] for p in priming)}, "development_usage": []}
    inspection = run / "runtime-inspection.json"
    if inspection.exists():
        public["runtime_inspection"] = json.loads(inspection.read_text(encoding="utf-8"))
        public["raw_sha256"][inspection.name] = sha(inspection)
    selected_index = acceptance["technical_selected_index"]
    if selected_index is not None:
        candidate = manifest["config"]["models"][selected_index]
        operating = {k: v for k, v in manifest["config"].items() if k != "models"}
        operating.update(model=candidate["name"], model_digest=candidate["digest"],
                         evidence_run=run.name, selection="provisional technical selection",
                         human_quality_review="pending", milestone_accepted=False,
                         limits_source="config/m2-limits.json")
        (ROOT/"config/m2-operating.json").write_text(json.dumps(operating, indent=2)+"\n", encoding="utf-8")
    for directory in args.development_runs:
        s = json.loads((directory/"summary.json").read_text(encoding="utf-8"))
        primes = json.loads((directory/"priming.json").read_text(encoding="utf-8"))
        public["development_usage"].append({"run": directory.name, "measured": s["overall"],
                                            "priming_n": len(primes),
                                            "priming_input_tokens": sum(p["prompt_eval_count"] for p in primes),
                                            "priming_output_tokens": sum(p["eval_count"] for p in primes)})
    target = ROOT / "docs/evidence"
    (target / "M2-results.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    lines = ["# M2 conversation review - pending", "",
             f"Run `{run.name}`. **The user has not reviewed or approved these samples.**", "",
             "Deterministic selection: every identity from the five-session warm profile, repetition 0 / seed 42, both candidates. "
             "No conversation was selected for being a good example. Full inputs and all repetitions remain in the ignored raw directory listed in [results](M2-results.json).", "",
             "Review each exchange for naturalness, character continuity, uncertainty, unsupported locations/items/actions/outcomes, and accidental knowledge of another identity. "
             "The fixture says a potion was lent; it does not say it was consumed or helped. No game action was executed.", "",
             "- [ ] Natural, believable player dialogue", "- [ ] Grounded facts and uncertainty", "- [ ] No invented completed actions or private knowledge",
             "- [ ] Accept a model/configuration or request a specific repair", ""]
    fixtures = json.loads((ROOT/"fixtures/m2-scenarios.json").read_text())
    for index in (0, 1):
        lines += [f"## Candidate {index}: {manifest['config']['models'][index]['name']}", ""]
        for session in range(5):
            identity = fixtures["identities"][session]
            selected = [r for r in rows if r["model_index"] == index and r["sessions"] == 5 and r["profile"] == "warm" and r["repeat"] == 0 and r["session"] == session and r["case"].startswith("conversation")]
            lines += [f"### {identity['name']} with {identity['friend']}", "",
                      "Supplied memory: promised to meet this friend at the west gate after resting; witnessed a loan of one red potion; "
                      "east-field safety is a stranger's unverified claim; previous movement timed out with arrival unknown; friend's inventory unknown.", ""]
            for row in selected:
                lines += [f"**{identity['friend']}:** {row['messages'][-1]['content'].split(': ', 1)[-1]}", "",
                          f"**{identity['name']}:** {row.get('content', row.get('error', 'missing'))}", ""]
    failures = [r for r in rows if r.get("score", {}).get("pass") is False or "error" in r or r.get("foreign_markers") or r.get("done_reason") == "length"]
    groups = {}
    for row in failures:
        key = json.dumps([row["model_index"], row["case"], row.get("content"), row.get("error"), row.get("score"), row.get("done_reason")], sort_keys=True)
        groups.setdefault(key, []).append(row)
    lines += ["## Automatic failures and truncations", "",
              f"{len(failures)} affected requests, grouped into {len(groups)} distinct case/output/result/finish combinations. "
              "Each group shows its exact first output and occurrence count; no repair or normalization. Every occurrence remains in the raw requests file.", ""]
    for group in groups.values():
        row = group[0]
        lines += [f"- {len(group)} occurrence(s); first `{row['phase']}`, identity {row['session']}, `{row['case']}`, finish `{row.get('done_reason')}`: `{json.dumps(row.get('score', {}))}`", "",
                  "```text", row.get("content", row.get("error", "missing")), "```", ""]
    (target / "M2-conversations.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(acceptance, indent=2))


if __name__ == "__main__":
    main()
