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
    parser.add_argument("--output-prefix", choices=("M2", "M2-retest"), default="M2")
    parser.add_argument("--prefer-model", type=int, choices=(0, 1))
    parser.add_argument("--comparison-run", type=Path)
    parser.add_argument("--diagnostic-run", type=Path)
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
    acceptance["preferred_index"] = args.prefer_model
    acceptance["technical_selected_index"] = (args.prefer_model if args.prefer_model in qualified else None) if args.prefer_model is not None else (min(qualified) if qualified else None)
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
    operating = {k: v for k, v in manifest["config"].items() if k != "models"}
    operating.update(model=None, model_digest=None, evidence_run=run.name,
                     selection="no selected configuration passes every fixed target",
                     human_quality_review="pending", milestone_accepted=False,
                     limits_source=manifest["args"]["limits"])
    if selected_index is not None:
        candidate = manifest["config"]["models"][selected_index]
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
    prefix = args.output_prefix
    lines = ["# M2 conversation review - pending", "",
             f"Run `{run.name}`. **The user has not reviewed or approved these samples.**", "",
             "Deterministic selection: every identity from the five-session warm profile, repetition 0 / seed 42, both candidates. "
             f"No conversation was selected for being a good example. Full inputs and all repetitions remain in the ignored raw directory listed in [results]({prefix}-results.json).", "",
             "Review each exchange for naturalness, character continuity, uncertainty, unsupported locations/items/actions/outcomes, and accidental knowledge of another identity. "
             "The fixture says a potion was lent; it does not say it was consumed or helped. No game action was executed.", "",
             "- [ ] Natural, believable player dialogue", "- [ ] Grounded facts and uncertainty", "- [ ] No invented completed actions or private knowledge",
             "- [ ] Accept a model/configuration or request a specific repair", ""]
    fixtures = json.loads((ROOT/manifest["args"].get("fixtures", "fixtures/m2-scenarios.json")).read_text())
    own_leaks = [row for row in rows if fixtures["identities"][row["session"]]["keepsake"].lower() in row.get("content", "").lower()]
    public["additional_diagnostics"] = {"own_private_marker_exposures": [
        {key: row[key] for key in ("model_index", "phase", "session", "case")} for row in own_leaks],
        "note": "Additional exact-marker diagnostic; not silently added to or substituted for the frozen foreign-marker metric. Outputs are preserved for quality review."}
    if "context" in fixtures:
        lines += ["The revised greeting receives only current_location=unknown. The second turn receives the unverified report, unconfirmed walk arrival, and unknown current location. "
                  "Loan/meeting memory remains available to recall and to specific diagnostic questions. Context scoping is declared in the fixture, not a working retrieval system.", ""]
    for index in (0, 1):
        lines += [f"## Candidate {index}: {manifest['config']['models'][index]['name']}", ""]
        for session in range(5):
            identity = fixtures["identities"][session]
            selected = [r for r in rows if r["model_index"] == index and r["sessions"] == 5 and r["profile"] == "warm" and r["repeat"] == 0 and r["session"] == session and r["case"].startswith("conversation")]
            lines += [f"### {identity['name']} with {identity['friend']}", "",
                      "Fixture memory (scoped by request): promised to meet this friend at the west gate after resting; witnessed a loan of one red potion; "
                      "east-field safety is a stranger's unverified claim; previous movement timed out with arrival unknown; friend's inventory unknown.", ""]
            for row in selected:
                lines += [f"**{identity['friend']}:** {row['messages'][-1]['content'].split(': ', 1)[-1]}", "",
                          f"**{identity['name']}:** {row.get('content', row.get('error', 'missing'))}", ""]
    failures = [r for r in rows if r.get("score", {}).get("pass") is False or "error" in r or r.get("foreign_markers") or r.get("done_reason") == "length" or r in own_leaks]
    groups = {}
    for row in failures:
        key = json.dumps([row["model_index"], row["case"], row.get("content"), row.get("error"), row.get("score"), row.get("done_reason")], sort_keys=True)
        groups.setdefault(key, []).append(row)
    lines += ["## Automatic failures, truncations and own private-marker exposures", "",
              f"{len(failures)} affected requests, grouped into {len(groups)} distinct case/output/result/finish combinations. "
              "Each group shows its exact first output and occurrence count; no repair or normalization. Every occurrence remains in the raw requests file.", ""]
    for group in groups.values():
        row = group[0]
        lines += [f"- {len(group)} occurrence(s); first `{row['phase']}`, identity {row['session']}, `{row['case']}`, finish `{row.get('done_reason')}`: `{json.dumps(row.get('score', {}))}`", "",
                  "```text", row.get("content", row.get("error", "missing")), "```", ""]
    if args.comparison_run:
        previous = [json.loads(line) for line in (args.comparison_run/"requests.jsonl").read_text(encoding="utf-8").splitlines()]
        previous_summary = json.loads((args.comparison_run/"summary.json").read_text(encoding="utf-8"))
        public["comparison"] = {"run": args.comparison_run.name,
                                "requests_sha256": sha(args.comparison_run/"requests.jsonl"),
                                "summary": {key: previous_summary[key] for key in ("overall", "groups", "resources", "m1")}}
        lines += ["## Original 9B replies and revised replies", "",
                  "Same player lines, seed 42, all five identities, warm five-session profile. The prompt/context differs as described above. No answer is omitted for poor quality.", ""]
        for new in rows:
            if new["model_index"] == 1 and new["sessions"] == 5 and new["profile"] == "warm" and new["repeat"] == 0 and new["case"].startswith("conversation"):
                old = next(row for row in previous if all(row[key] == new[key] for key in ("model_index", "sessions", "profile", "repeat", "session", "case")))
                assert old["messages"][-1] == new["messages"][-1]
                lines += [f"### Identity {new['session']}, {new['case']}", "",
                          f"**Player:** {new['messages'][-1]['content']}", "",
                          f"**Original:** {old.get('content', old.get('error'))}", "",
                          f"**Revised:** {new.get('content', new.get('error'))}", ""]
    if args.diagnostic_run:
        diagnostic = args.diagnostic_run
        dm = json.loads((diagnostic/"manifest.json").read_text(encoding="utf-8"))
        for path, expected in dm["source_hashes"].items():
            if sha(ROOT/path) != expected:
                raise RuntimeError(f"diagnostic source changed: {path}")
        dr = [json.loads(line) for line in (diagnostic/"requests.jsonl").read_text(encoding="utf-8").splitlines()]
        df = json.loads((ROOT/dm["args"]["fixtures"]).read_text())
        assert dm["args"]["models"] == [1] and dm["args"]["profiles"] == [1] and dm["args"]["repeats"] == 3
        expected = {(case["id"], profile, seed) for case in df["cases"] for profile in ("cold", "warm") for seed in (42,43,44)}
        assert len(dr) == len(expected) and {(row["case"],row["profile"],row["seed"]) for row in dr} == expected
        dp = json.loads((diagnostic/"priming.json").read_text())
        public["diagnostics"] = {"run": diagnostic.name, "source_commit": dm["source_commit"],
                                 "source_hashes": dm["source_hashes"], "args": dm["args"],
                                 "summary": json.loads((diagnostic/"summary.json").read_text()),
                                 "raw_sha256": {file: sha(diagnostic/file) for file in ("manifest.json","requests.jsonl","resources.jsonl","summary.json","priming.json")},
                                 "rubrics": [{"case": c["id"], "split": c["split"], "rubric": c["rubric"]} for c in df["cases"]],
                                 "priming_usage": {"n": len(dp), "input_tokens": sum(p["prompt_eval_count"] for p in dp), "output_tokens": sum(p["eval_count"] for p in dp)},
                                 "human_review": "pending", "automated_semantic_grade": None}
        lines += ["## Grounding diagnostic replies - all cases and seeds", "",
                  "Three development cases and eight first sampled after the freeze (including three positive controls). "
                  "Each case ran cold/warm with seeds 42/43/44. Exact duplicate outputs are grouped with every profile/seed listed. "
                  "Rubrics were never sent as answer text. No automatic semantic grade or human approval is assigned.", ""]
        for case in df["cases"]:
            lines += [f"### {case['id']} ({case['split']})", "",
                      f"**Player:** {case['user']}", "",
                      f"**Expected grounding:** {' '.join(case['rubric']['required'])}", "",
                      f"**Unsupported:** {' '.join(case['rubric']['unsupported'])}", ""]
            outputs = {}
            for row in dr:
                if row["case"] == case["id"]:
                    outputs.setdefault(row.get("content",row.get("error")),[]).append(f"{row['profile']}/seed{row['seed']}")
            for content, refs in outputs.items():
                lines += [f"- {', '.join(refs)}:", "", "> " + content.replace("\n", "\n> "), ""]
    (target / f"{prefix}-results.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    (target / f"{prefix}-conversations.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps(acceptance, indent=2))


if __name__ == "__main__":
    main()
