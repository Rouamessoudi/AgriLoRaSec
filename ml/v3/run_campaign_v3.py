#!/usr/bin/env python3
"""Campagne dataset_v3 : 4 tailles x 96 runs x 1800s. Pas de ML."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/home/opp_env/AgriLoRaSec")
SIM = ROOT / "simulations"
BIN = ROOT / "out/clang-release/src/AgriLoRaSec"
V3 = ROOT / "ml" / "v3"
RAW = V3 / "raw"
FEAT = V3 / "features"
REPORTS = V3 / "reports"
BUILD = V3 / "build_dataset_v3.py"

NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]
SIM_TIME = os.environ.get("V3_SIM_TIME", "1800s")
SEEDS = [0, 1, 2, 3]
SFS = [7, 8, 9, 10, 11, 12]
SCENARIOS = ["Normal", "Jamming", "Replay", "Wormhole"]
SIZES = [10, 20, 30, 50]
ATTACK_START = 360.0
ATTACK_END = 1440.0
WINDOW_S = 60.0

CONFIG_BY_N = {
    10: {"Normal": "NoAttack", "Jamming": "Jamming", "Replay": "Replay", "Wormhole": "Wormhole"},
    20: {"Normal": "NoAttack20", "Jamming": "Jamming20", "Replay": "Replay20", "Wormhole": "Wormhole20"},
    30: {"Normal": "NoAttack30", "Jamming": "Jamming30", "Replay": "Replay30", "Wormhole": "Wormhole30"},
    50: {"Normal": "NoAttack50", "Jamming": "Jamming50", "Replay": "Replay50", "Wormhole": "Wormhole50"},
}

V12_FILES = [
    ROOT / "ml/v2/features/dataset_v2_10nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_20nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_30nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_50nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_all_nodes.csv",
    ROOT / "ml/v2/build_dataset_v2.py",
    ROOT / "ml/dataset.csv",
    ROOT / "ml/dataset_20nodes.csv",
    ROOT / "src/ReplayApp.cc",
    ROOT / "src/WormholeApp.cc",
    ROOT / "src/JammerApp.cc",
    ROOT / "src/PreserveHeaderLoRaMac.cc",
    Path("/home/opp_env/flora-1.2.0/src/LoRa/LoRaMac.cc"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def snapshot():
    return {str(p): md5(p) for p in V12_FILES if p.is_file()}


def stem_for(n: int, scenario: str, sf: int, seed: int) -> str:
    return f"{CONFIG_BY_N[n][scenario]}_sf{sf}_s{seed}"


def sf_overrides(sf: int) -> list[str]:
    s = str(sf)
    return [
        f"--**.loRaNode*.app[0].initialLoRaSF={s}",
        f"--**.jammer.app[0].initialLoRaSF={s}",
        f"--**.replayer.app[0].initialLoRaSF={s}",
        f"--**.wormholeA.app[0].initialLoRaSF={s}",
        f"--**.wormholeB.app[0].initialLoRaSF={s}",
    ]


def job_paths(n: int, scenario: str, sf: int, seed: int):
    stem = stem_for(n, scenario, sf, seed)
    d = RAW / f"{n}nodes"
    return {
        "stem": stem, "n": n, "scenario": scenario, "sf": sf, "seed": seed,
        "cfg": CONFIG_BY_N[n][scenario],
        "csv": d / f"{stem}.csv", "log": d / f"{stem}.log", "okflag": d / f"{stem}.ok",
    }


def is_done(job: dict) -> bool:
    if not job["csv"].exists() or job["csv"].stat().st_size <= 20:
        return False
    if not job["log"].exists():
        return False
    t = job["log"].read_text(errors="replace")
    return "Simulation time limit reached -- at t=1800s" in t and "Error:" not in t


def run_job(job: dict) -> dict:
    if is_done(job):
        return {"stem": job["stem"], "status": "skip", "n": job["n"]}
    job["csv"].parent.mkdir(parents=True, exist_ok=True)
    sca = f"results/v3_{job['stem']}.sca"
    vec = f"results/v3_{job['stem']}.vec"
    cmd = [
        str(BIN), "-u", "Cmdenv", "-c", job["cfg"],
        f"--sim-time-limit={SIM_TIME}",
        "--cmdenv-express-mode=true",
        f"--seed-set={job['seed']}",
        f"--output-scalar-file={sca}",
        f"--output-vector-file={vec}",
        "--**.vector-recording=false",
        '--**.packetEventLogger.outputFile="results/%s.csv"' % job["stem"],
        "-n", NED,
    ] + sf_overrides(job["sf"]) + LIBS
    src_csv = SIM / "results" / f"{job['stem']}.csv"
    t0 = time.time()
    with job["log"].open("w") as f:
        proc = subprocess.run(cmd, cwd=str(SIM), stdout=f, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    logtxt = job["log"].read_text(errors="replace") if job["log"].exists() else ""
    if src_csv.exists():
        shutil.copy2(src_csv, job["csv"])
    ok = (
        proc.returncode == 0
        and "Simulation time limit reached -- at t=1800s" in logtxt
        and "Error:" not in logtxt
        and job["csv"].exists()
        and job["csv"].stat().st_size > 20
    )
    if ok:
        job["okflag"].write_text(f"ok dt={dt:.1f}\n")
        return {"stem": job["stem"], "status": "ok", "n": job["n"], "dt": dt, "rc": proc.returncode}
    err = ""
    for line in logtxt.splitlines():
        if "Error:" in line or "syntax error" in line:
            err = line[:240]
            break
    return {
        "stem": job["stem"], "status": "fail", "n": job["n"], "dt": dt,
        "rc": proc.returncode, "err": err or logtxt[-400:],
    }


def all_jobs():
    jobs = []
    for n in SIZES:
        (RAW / f"{n}nodes").mkdir(parents=True, exist_ok=True)
        for sc in SCENARIOS:
            for sf in SFS:
                for seed in SEEDS:
                    jobs.append(job_paths(n, sc, sf, seed))
    return jobs


def run_pool(pending, workers):
    results, fails = [], []
    if not pending:
        return results, fails
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_job, j): j["stem"] for j in pending}
        done_n = 0
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done_n += 1
            if r["status"] == "fail":
                fails.append(r)
                print(f"FAIL {r['stem']} {str(r.get('err', ''))[:180]}", flush=True)
            if done_n % 4 == 0 or r["status"] != "skip":
                print(f"progress {done_n}/{len(pending)} last={r['stem']} {r['status']}", flush=True)
    return results, fails


def build_features():
    for n in SIZES:
        out = FEAT / f"dataset_v3_{n}nodes.csv"
        subprocess.run(
            [
                sys.executable, str(BUILD),
                "--raw-dir", str(RAW / f"{n}nodes"),
                "--out-csv", str(out),
                "--only-n-nodes", str(n),
                "--report-name", f"dataset_v3_{n}nodes_report.txt",
            ],
            check=True,
        )


def concat_all():
    rows, header = [], None
    for n in SIZES:
        p = FEAT / f"dataset_v3_{n}nodes.csv"
        with p.open(newline="") as f:
            r = csv.DictReader(f)
            header = r.fieldnames
            rows.extend(list(r))
    dest = FEAT / "dataset_v3_all_nodes.csv"
    with dest.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return dest, len(rows)


def ffloat(x):
    if x is None or x == "":
        return math.nan
    try:
        return float(x)
    except ValueError:
        return math.nan


def summarize():
    raw_stats = {}
    base_raw = None
    for n in SIZES:
        tot = d = c = o = 0
        nfiles = 0
        for p in (RAW / f"{n}nodes").glob("*.csv"):
            if p.name.endswith(".meta.csv"):
                continue
            nfiles += 1
            with p.open(newline="") as f:
                for row in csv.DictReader(f):
                    tot += 1
                    rec = float(row.get("received") or 0)
                    col = float(row.get("collision") or 0)
                    if rec >= 1:
                        d += 1
                    elif col >= 1:
                        c += 1
                    elif rec == 0:
                        o += 1
        usable = d + c
        rec = {"runs": nfiles, "raw_rows": tot, "rx_gw": d, "collisions_gw": c, "gw_usable": usable, "omniscient": o}
        if n == 10:
            base_raw = tot or 1
        rec["ratio_vs_10"] = tot / base_raw if base_raw else None
        raw_stats[n] = rec

    feat_stats = {}
    for n in SIZES + ["all"]:
        name = f"dataset_v3_{n}nodes.csv" if n != "all" else "dataset_v3_all_nodes.csv"
        p = FEAT / name
        with p.open(newline="") as f:
            rows = list(csv.DictReader(f))
        labels = defaultdict(int)
        run_ids = set()
        scenarios = defaultdict(int)
        sfs = set()
        seeds = set()
        for r in rows:
            labels[r["Label"]] += 1
            run_ids.add(r["run_id"])
            scenarios[r["scenario"]] += 1
            sfs.add(r["SF"])
            seeds.add(r["seed"])
        feat_stats[str(n)] = {
            "rows": len(rows), "unique_run_id": len(run_ids),
            "labels": dict(labels), "windows_per_run": (len(rows) / len(run_ids) if run_ids else None),
            "sfs": sorted(sfs), "seeds": sorted(seeds),
        }

    attack = {}
    for n in SIZES:
        p = FEAT / f"dataset_v3_{n}nodes.csv"
        with p.open(newline="") as f:
            rows = list(csv.DictReader(f))
        by_lab = defaultdict(list)
        for r in rows:
            by_lab[r["Label"]].append(r)
        jam = by_lab["Jamming"]
        def mean_feat(rs, k):
            xs = [ffloat(r[k]) for r in rs]
            xs = [x for x in xs if not math.isnan(x)]
            return sum(xs) / len(xs) if xs else None
        def dup_stats(lab):
            rs = by_lab[lab]
            n_pos = sum(1 for r in rs if not math.isnan(ffloat(r["duplicate_rate"])) and ffloat(r["duplicate_rate"]) > 0)
            runs_dup = set()
            for r in rs:
                if not math.isnan(ffloat(r["duplicate_rate"])) and ffloat(r["duplicate_rate"]) > 0:
                    runs_dup.add(r["run_id"])
            n_runs = len({r["run_id"] for r in rs})
            return {
                "active_windows": len(rs),
                "windows_dup_gt0": n_pos,
                "pct_dup_gt0": (100.0 * n_pos / len(rs) if rs else 0),
                "runs_with_gw_dup": len(runs_dup),
                "n_runs_label": n_runs,
            }
        attack[n] = {
            "jamming_packet_rate_mean": mean_feat(jam, "packet_rate"),
            "jamming_collision_intensity_mean": mean_feat(jam, "collision_intensity"),
            "replay": dup_stats("Replay"),
            "wormhole": dup_stats("Wormhole"),
        }
    return {"raw": raw_stats, "features": feat_stats, "attacks": attack}


def main():
    workers = int(os.environ.get("V3_WORKERS", "4"))
    FEAT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    (REPORTS / "v12_hashes_before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    jobs = all_jobs()
    assert len(jobs) == 384, len(jobs)
    pending = [j for j in jobs if not is_done(j)]
    print(f"jobs={len(jobs)} pending={len(pending)} workers={workers}", flush=True)
    results, fails = run_pool(pending, workers)
    still = [j for j in all_jobs() if not is_done(j)]
    if still:
        print(f"retry {len(still)} failed/missing runs once", flush=True)
        _, fails2 = run_pool(still, workers)
        fails = fails2
    still = [j["stem"] for j in all_jobs() if not is_done(j)]
    (REPORTS / "campaign_run_status.json").write_text(
        json.dumps({"fails": fails, "still": still, "n_jobs": len(jobs)}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"still_missing={len(still)} fails={len(fails)}", flush=True)
    if still:
        after = snapshot()
        (REPORTS / "v12_hashes_after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
        print("DATASET_V3_FINAL_NOT_READY", flush=True)
        return 2
    print("building features...", flush=True)
    build_features()
    dest, n = concat_all()
    print(f"concat {dest} rows={n}", flush=True)
    summary = summarize()
    after = snapshot()
    summary["v12_hashes_unchanged"] = before == after
    summary["hashes_before"] = before
    summary["hashes_after"] = after
    summary["n_jobs"] = 384
    summary["missing"] = still
    (REPORTS / "v3_final_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("raw", "features", "attacks", "v12_hashes_unchanged")}, indent=2), flush=True)
    (REPORTS / "campaign_DONE").write_text("ok\n")
    print("DATASET_V3_FINAL_READY", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
