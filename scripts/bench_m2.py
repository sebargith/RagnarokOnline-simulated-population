"""Reproduce M2 cold/warm session bursts beside M1. Raw results stay in runtime/."""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge
from inference.m2 import BoundedInference, api, score, stream_chat


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MemoryStatus(ct.Structure):
    _fields_ = [("length", wt.DWORD), ("load", wt.DWORD)] + [
        (key, ct.c_ulonglong) for key in ("total", "available", "page_total", "page_available",
                                        "virtual_total", "virtual_available", "extended")]


class ProcessMemory(ct.Structure):
    _fields_ = [("cb", wt.DWORD), ("faults", wt.DWORD)] + [
        (key, ct.c_size_t) for key in ("peak_ws", "ws", "quota_peak_paged", "quota_paged",
                                      "quota_peak_nonpaged", "quota_nonpaged", "pagefile",
                                      "peak_pagefile", "private")]


def ram_sample(project_pids):
    kernel, psapi = ct.windll.kernel32, ct.windll.psapi
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)]
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ct.POINTER(ProcessMemory), wt.DWORD]
    memory = MemoryStatus(length=ct.sizeof(MemoryStatus))
    if not kernel.GlobalMemoryStatusEx(ct.byref(memory)):
        raise ct.WinError()
    ids, needed = (wt.DWORD * 8192)(), wt.DWORD()
    if not psapi.EnumProcesses(ids, ct.sizeof(ids), ct.byref(needed)):
        raise ct.WinError()
    groups = {name: {"ws": 0, "private": 0, "pids": []} for name in ("ollama", "m1")}
    for pid in list(ids)[:needed.value // ct.sizeof(wt.DWORD)]:
        handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
        if not handle:
            continue
        try:
            name, size = ct.create_unicode_buffer(32768), wt.DWORD(32768)
            if not kernel.QueryFullProcessImageNameW(handle, 0, name, ct.byref(size)):
                continue
            group = "m1" if pid in project_pids else "ollama" if "ollama" in name.value.lower() else None
            if group:
                counters = ProcessMemory(cb=ct.sizeof(ProcessMemory))
                if not psapi.GetProcessMemoryInfo(handle, ct.byref(counters), ct.sizeof(counters)):
                    raise ct.WinError()
                groups[group]["ws"] += counters.ws
                groups[group]["private"] += counters.private
                groups[group]["pids"].append(pid)
        finally:
            kernel.CloseHandle(handle)
    return {"ram_total": memory.total, "ram_available": memory.available,
            "ram_used": memory.total - memory.available, **groups}


class Monitor:
    def __init__(self, output, config):
        self.output, self.config = output, config
        self.phase = "initial"
        self.samples, self.errors = [], []
        self.stop = threading.Event()
        self.violation = threading.Event()
        self.bridges = {}
        self.bridge_stats = {}
        registry = json.loads((ROOT / "runtime/processes.json").read_text())
        self.pids = {v["pid"] for v in registry.values()}
        for who in ("agent", "peer"):
            self.bridges[who] = Bridge(ROOT / "runtime/openkore" / who / "bridge.json")
            self.bridge_stats[who] = {"snapshots": 0, "disconnected": 0, "max_gap_s": 0, "last": None}
        self.threads = [threading.Thread(target=self._resources, daemon=True),
                        threading.Thread(target=self._bridges, daemon=True)]

    def start(self):
        for thread in self.threads:
            thread.start()
        # Obtain initial samples and connected snapshots before any model load.
        deadline = time.monotonic() + 8
        while not self.samples or any(s["snapshots"] == 0 for s in self.bridge_stats.values()):
            if self.errors or time.monotonic() > deadline:
                raise RuntimeError(f"monitor unavailable: {self.errors}")
            time.sleep(.05)

    def _resources(self):
        with (self.output / "resources.jsonl").open("w", encoding="utf-8") as raw:
            while not self.stop.is_set():
                try:
                    row = {"time": time.time(), "phase": self.phase, **ram_sample(self.pids)}
                    gpu = subprocess.check_output([
                        "nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
                        "--format=csv,noheader,nounits"], text=True, timeout=3,
                        creationflags=subprocess.CREATE_NO_WINDOW).strip().split(",")
                    row.update(gpu_used_mib=int(gpu[0]), gpu_total_mib=int(gpu[1]),
                               gpu_utilization=int(gpu[2]), gpu_temperature=int(gpu[3]))
                    self.samples.append(row)
                    raw.write(json.dumps(row) + "\n")
                    raw.flush()
                    if row["ram_available"] < self.config["min_available_ram_gib"] * 1024**3 or row["gpu_used_mib"] > self.config["max_gpu_used_mib"]:
                        self.violation.set()
                except Exception as error:
                    self.errors.append("resources: " + repr(error))
                    self.violation.set()
                self.stop.wait(1)

    def _bridges(self):
        try:
            while not self.stop.is_set():
                for who, bridge in self.bridges.items():
                    for event in bridge.poll(.05):
                        if event["kind"] == "snapshot":
                            stat = self.bridge_stats[who]
                            now = time.monotonic()
                            if stat["last"]:
                                stat["max_gap_s"] = max(stat["max_gap_s"], now-stat["last"])
                            stat["last"] = now
                            stat["snapshots"] += 1
                            stat["disconnected"] += not event["data"]["connected"]
                    bridge.drain()
        except Exception as error:
            self.errors.append("bridge: " + repr(error))
            self.violation.set()

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(5)
        for bridge in self.bridges.values():
            bridge.close()

    def summary(self, phase=None):
        rows = [s for s in self.samples if phase is None or s["phase"] == phase]
        if not rows:
            return {"samples": 0}
        return {"samples": len(rows), "min_available_ram_gib": min(s["ram_available"] for s in rows)/1024**3,
                "peak_system_used_gib": max(s["ram_used"] for s in rows)/1024**3,
                "peak_ollama_ws_gib": max(s["ollama"]["ws"] for s in rows)/1024**3,
                "peak_ollama_private_gib": max(s["ollama"]["private"] for s in rows)/1024**3,
                "peak_m1_ws_mib": max(s["m1"]["ws"] for s in rows)/1024**2,
                "peak_gpu_used_mib": max(s["gpu_used_mib"] for s in rows)}


def unload(config, model):
    api(config["endpoint"], "/api/generate", {"model": model, "keep_alive": 0})
    deadline = time.monotonic() + 10
    while api(config["endpoint"], "/api/ps")["models"]:
        if time.monotonic() > deadline:
            raise RuntimeError("runner did not unload (or unrelated model loaded)")
        time.sleep(.1)


def stats(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(values), "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "p50": statistics.median(values), "p95": ordered[max(0, math.ceil(.95*len(values))-1)],
            "max": max(values)}


def summarize(rows):
    good = [r for r in rows if "error" not in r]
    result = {"n": len(rows), "failures": len(rows)-len(good),
              "automatic_checks": sum(r.get("score", {}).get("pass") is not None for r in good),
              "automatic_failures": sum(r.get("score", {}).get("pass") is False for r in good),
              "leaks": sum(bool(r.get("foreign_markers")) for r in good),
              "truncations": sum(r.get("done_reason") == "length" for r in good),
              "input_tokens": sum(r.get("prompt_eval_count", 0) for r in good),
              "output_tokens": sum(r.get("eval_count", 0) for r in good)}
    for key in ("ttft_s", "service_s", "queue_s", "response_s", "prompt_eval_count", "eval_count"):
        result[key] = stats([r[key] for r in good if r.get(key) is not None])
    result["cold_load_s"] = stats([r["load_duration"]/1e9 for r in good if r.get("cold_request")])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/m2-candidates.json")
    parser.add_argument("--limits", default="config/m2-limits.json")
    parser.add_argument("--models", nargs="+", type=int, choices=(0, 1), default=[0, 1])
    parser.add_argument("--profiles", nargs="+", type=int, choices=(1, 3, 5), default=[1, 3, 5])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--label", default="development")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error("repeats must be 1..5")
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text())
    fixtures = json.loads((ROOT / "fixtures/m2-scenarios.json").read_text())
    output = ROOT / "runtime/evidence" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-m2-" + args.label)
    output.mkdir(parents=True)
    print(str(output), flush=True)
    endpoint = config["endpoint"]
    version = api(endpoint, "/api/version")
    if version["version"] != config["runtime_version"]:
        raise RuntimeError("runtime version differs from pin")
    if api(endpoint, "/api/ps")["models"]:
        raise RuntimeError("benchmark requires no preloaded model; preserve other users' runners")
    tags = api(endpoint, "/api/tags")["models"]
    metadata = {"args": vars(args), "config": config, "version": version, "models": [],
                "limits": json.loads((ROOT / args.limits).read_text()),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "source_hashes": {path: digest(ROOT/path) for path in (
                    "inference/m2.py", "scripts/bench_m2.py", "fixtures/m2-scenarios.json", args.config, args.limits)},
                "python": sys.version}
    for index in args.models:
        model = config["models"][index]
        tag = next(t for t in tags if t["name"] == model["name"])
        if tag["digest"] != model["digest"]:
            raise RuntimeError("model artifact differs from pin")
        metadata["models"].append({"tag": tag, "show": api(endpoint, "/api/show", {"model": model["name"]})})
    save(output / "manifest.json", metadata)
    monitor = Monitor(output, config)
    rows, priming, phases = [], [], []
    model = None
    fatal = None
    try:
        monitor.start()
        for index in args.models:
            model = config["models"][index]["name"]
            for sessions in args.profiles:
                for temperature in ("cold", "warm"):
                    for repeat in range(args.repeats):
                        if monitor.violation.is_set():
                            raise RuntimeError("resource/monitor guard tripped")
                        phase = f"model{index}/{sessions}/{temperature}/{repeat}"
                        monitor.phase = phase
                        unload(config, model)
                        if temperature == "warm":
                            prime = stream_chat(config, model, [{"role": "user", "content": "Reply with Hi."}], 42, True)
                            priming.append({"phase": phase, **prime})
                        scheduler = BoundedInference(config, model)
                        histories = [[] for _ in range(sessions)]
                        try:
                            for turn, case in enumerate(fixtures["cases"]):
                                pending = []
                                for session in range(sessions):
                                    if monitor.violation.is_set():
                                        raise RuntimeError("resource/monitor guard tripped")
                                    identity = fixtures["identities"][session]
                                    system = fixtures["system"].format(**identity)
                                    # Action JSON includes braces; substitute identity placeholders only.
                                    user = case["user"].replace("{friend}", identity["friend"])
                                    history = histories[session] if case["kind"] == "conversation" else []
                                    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user}]
                                    cold = temperature == "cold" and turn == 0 and session == 0
                                    future = scheduler.submit(str(session), messages, 42+repeat, cold, case.get("format"))
                                    pending.append((session, identity, user, messages, cold, future))
                                for session, identity, user, messages, cold, future in pending:
                                    response = future.result(timeout=config["cold_request_deadline_s"] + 2)
                                    row = {"phase": phase, "model_index": index, "sessions": sessions,
                                           "profile": temperature, "repeat": repeat, "session": session,
                                           "case": case["id"], "cold_request": cold,
                                           "messages": messages, "format": case.get("format"), "seed": 42+repeat, **response}
                                    if "error" not in response:
                                        row["score"] = score(case, identity, response["content"])
                                        row["foreign_markers"] = [other["keepsake"] for other in fixtures["identities"]
                                                                  if other != identity and other["keepsake"] in response["content"]]
                                        if case["kind"] == "conversation":
                                            histories[session] += [{"role": "user", "content": user},
                                                                   {"role": "assistant", "content": response["content"]}]
                                    rows.append(row)
                                    with (output / "requests.jsonl").open("a", encoding="utf-8") as raw:
                                        raw.write(json.dumps(row, ensure_ascii=False) + "\n")
                                if scheduler.circuit.is_set():
                                    raise RuntimeError("inference circuit opened; no retry")
                            loaded = api(endpoint, "/api/ps")
                            # Ensure enough time for at least one post-load resource sample.
                            time.sleep(1.1)
                            phases.append({"phase": phase, "loaded": loaded})
                            phase_summary = summarize([r for r in rows if r["phase"] == phase])
                            print(json.dumps({"phase": phase, "n": phase_summary["n"],
                                              "failures": phase_summary["failures"],
                                              "automatic_failures": phase_summary["automatic_failures"],
                                              "response_p95_s": phase_summary["response_s"]["p95"]}), flush=True)
                        finally:
                            scheduler.close()
                        unload(config, model)
    except Exception as error:
        fatal = repr(error)
        print("STOP: " + fatal, flush=True)
    finally:
        if model is not None:
            try:
                unload(config, model)
            except Exception as error:
                monitor.errors.append("cleanup: " + repr(error))
        monitor.close()
        summary = {"fatal": fatal, "overall": summarize(rows), "resources": monitor.summary(),
                   "monitor_errors": monitor.errors, "resource_guard_tripped": monitor.violation.is_set(),
                   "m1": monitor.bridge_stats, "groups": []}
        for index in args.models:
            for sessions in args.profiles:
                for temperature in ("cold", "warm"):
                    subset = [r for r in rows if r["model_index"] == index and r["sessions"] == sessions and r["profile"] == temperature]
                    if subset:
                        summary["groups"].append({"model_index": index, "sessions": sessions,
                                                  "profile": temperature, **summarize(subset)})
        summary["phase_resources"] = [{"phase": p["phase"], **monitor.summary(p["phase"]), "loaded": p["loaded"]} for p in phases]
        save(output / "summary.json", summary)
        save(output / "priming.json", priming)
        print(json.dumps({"output": str(output), "overall": summary["overall"], "fatal": fatal}), flush=True)
    if fatal or monitor.errors or monitor.violation.is_set():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
