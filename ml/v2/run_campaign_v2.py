#!/usr/bin/env python3
"""Campagne finale dataset_v2 : 4 tailles x 96 runs x 1800s. Pas de ML."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/home/opp_env/AgriLoRaSec")
SIM = ROOT / "simulations"
BIN = ROOT / "out/clang-release/src/AgriLoRaSec"
V2 = ROOT / "ml" / "v2"
RAW = V2 / "raw"
FEAT = V2 / "features"
REPORTS = V2 / "reports"
BUILD = V2 / "build_dataset_v2.py"

NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]
SIM_TIME = os.environ.get("V2_SIM_TIME", "1800s")
SEEDS = [0, 1, 2, 3]
SFS = [7, 8, 9, 10, 11, 12]
SCENARIOS = ["Normal", "Jamming", "Replay", "Wormhole"]
SIZES = [10, 20, 30, 50]

CONFIG_BY_N = {
    10: {"Normal": "NoAttack", "Jamming": "Jamming", "Replay": "Replay", "Wormhole": "Wormhole"},
    20: {"Normal": "NoAttack20", "Jamming": "Jamming20", "Replay": "Replay20", "Wormhole": "Wormhole20"},
    30: {"Normal": "NoAttack30", "Jamming": "Jamming30", "Replay": "Replay30", "Wormhole": "Wormhole30"},
    50: {"Normal": "NoAttack50", "Jamming": "Jamming50", "Replay": "Replay50", "Wormhole": "Wormhole50"},
}

INTEGRITY = [
    ROOT / "src/ReplayApp.cc",
    ROOT / "src/WormholeApp.cc",
    ROOT / "src/JammerApp.cc",
    ROOT / "src/PreserveHeaderLoRaMac.cc",
    ROOT / "src/PacketEventLogger.cc",
    Path("/home/opp_env/flora-1.2.0/src/LoRa/LoRaMac.cc"),
    SIM / "package.ned",
    SIM / "AgriLoRaNetwork20.ned",
    SIM / "AgriLoRaNetwork30.ned",
    SIM / "AgriLoRaNetwork50.ned",
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def stem_for(n: int, scenario: str, sf: int, seed: int) -> str:
    cfg = CONFIG_BY_N[n][scenario]
    # Fichier : Jamming_sf7_s0 (10) / Jamming20_sf7_s0 (20+)
    return f"{cfg}_sf{sf}_s{seed}"


def sf_overrides(sf: int) -> list[str]:
    s = str(sf)
    return [
        f"--**.loRaNode*.**initialLoRaSF={s}",
        f"--**.loRaNode*.app[0].initialLoRaSF={s}",
        f"--**.jammer.**initialLoRaSF={s}",
        f"--**.jammer.app[0].initialLoRaSF={s}",
        f"--**.replayer.**initialLoRaSF={s}",
        f"--**.replayer.app[0].initialLoRaSF={s}",
        f"--**.wormholeA.**initialLoRaSF={s}",
        f"--**.wormholeB.**initialLoRaSF={s}",
        f"--**.wormholeA.app[0].initialLoRaSF={s}",
        f"--**.wormholeB.app[0].initialLoRaSF={s}",
    ]


def job_paths(n: int, scenario: str, sf: int, seed: int):
    stem = stem_for(n, scenario, sf, seed)
    d = RAW / f"{n}nodes"
    return {
        "stem": stem,
        "n": n,
        "scenario": scenario,
        "sf": sf,
        "seed": seed,
        "cfg": CONFIG_BY_N[n][scenario],
        "csv": d / f"{stem}.csv",
        "log": d / f"{stem}.log",
        "okflag": d / f"{stem}.ok",
    }


def is_done(job: dict) -> bool:
    if not job["csv"].exists() or job["csv"].stat().st_size <= 20:
        return False
    if not job["log"].exists():
        return False
    t = job["log"].read_text(errors="replace")
    if "Simulation time limit reached -- at t=1800s" in t:
        job["okflag"].write_text("ok\n")
        return True
    return False


def run_job(job: dict) -> dict:
    if is_done(job):
        return {"stem": job["stem"], "status": "skip", "n": job["n"]}
    job["csv"].parent.mkdir(parents=True, exist_ok=True)
    rel_log = job["log"]
    sca = f"results/v2_{job['stem']}.sca"
    vec = f"results/v2_{job['stem']}.vec"
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
    with rel_log.open("w") as f:
        proc = subprocess.run(cmd, cwd=str(SIM), stdout=f, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    logtxt = rel_log.read_text(errors="replace") if rel_log.exists() else ""
    if src_csv.exists():
        shutil.copy2(src_csv, job["csv"])
    elif (SIM / "results" / "packet_events.csv").exists() and proc.returncode == 0:
        shutil.copy2(SIM / "results" / "packet_events.csv", job["csv"])
    ok = proc.returncode == 0 and "Simulation time limit reached -- at t=1800s" in logtxt and job["csv"].exists()
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
        "rc": proc.returncode, "err": err or logtxt[-500:],
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


def write_integrity(tag: str):
    data = {str(p): md5(p) for p in INTEGRITY if p.exists()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"integrity_{tag}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def build_features():
    for n in SIZES:
        out = FEAT / f"dataset_v2_{n}nodes.csv"
        subprocess.run(
            [
                sys.executable, str(BUILD),
                "--raw-dir", str(RAW / f"{n}nodes"),
                "--out-csv", str(out),
                "--only-n-nodes", str(n),
                "--report-name", f"dataset_v2_{n}nodes_report.txt",
            ],
            check=True,
        )


def concat_all():
    outs = [FEAT / f"dataset_v2_{n}nodes.csv" for n in SIZES]
    rows = []
    header = None
    for p in outs:
        with p.open(newline="") as f:
            r = csv.DictReader(f)
            header = r.fieldnames
            rows.extend(list(r))
    dest = FEAT / "dataset_v2_all_nodes.csv"
    with dest.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return dest, len(rows)


def main():
    workers = int(os.environ.get("V2_WORKERS", "4"))
    write_integrity("before")
    jobs = all_jobs()
    pending = [j for j in jobs if not is_done(j)]
    maxj = os.environ.get("V2_MAX_JOBS")
    if maxj:
        pending = pending[: int(maxj)]
        print(f"V2_MAX_JOBS={maxj}", flush=True)
    print(f"jobs={len(jobs)} pending={len(pending)} workers={workers}", flush=True)
    results = []
    fails = []
    if pending:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_job, j): j["stem"] for j in pending}
            done_n = 0
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                done_n += 1
                if r["status"] == "fail":
                    fails.append(r)
                    print(f"FAIL {r['stem']} {r.get('err', '')[:180]}", flush=True)
                if done_n % 8 == 0 or r["status"] != "skip":
                    print(f"progress {done_n}/{len(pending)} last={r['stem']} {r['status']}", flush=True)
    still = [j["stem"] for j in all_jobs() if not is_done(j)]
    print(f"still_missing={len(still)} fails={len(fails)}", flush=True)
    (REPORTS / "campaign_run_status.json").write_text(
        json.dumps({"fails": fails, "still": still, "n_jobs": len(jobs)}, indent=2, default=str),
        encoding="utf-8",
    )
    if still:
        print("NOT all runs complete; skip feature build", flush=True)
        write_integrity("after_partial")
        return 2
    print("building features...", flush=True)
    build_features()
    dest, n = concat_all()
    print(f"concat {dest} rows={n}", flush=True)
    write_integrity("after")
    (REPORTS / "campaign_DONE").write_text("ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
