#!/usr/bin/env python3
"""Dataset V3 : W=60s, labels par fenetre programmee 360-1440. Pas de ML."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
FEATURES_DIR = HERE / "features"
REPORTS_DIR = HERE / "reports"

WINDOW_S = 60.0
ATTACK_START_S = 360.0
ATTACK_END_S = 1440.0
EXPECTED_WINDOWS = 30

FEATURES_X = [
    "packet_rate",
    "gw_success_rate",
    "collision_rate",
    "collision_intensity",
    "duplicate_rate",
    "mean_duplicate_delay_s",
    "min_duplicate_delay_s",
    "max_duplicate_delay_s",
    "mean_rssi",
    "std_rssi",
    "mean_snir",
    "std_snir",
    "interarrival_mean",
    "interarrival_std",
]

FORBIDDEN_IN_X = {
    "sender_name", "sender_mac", "sequence_number", "Label", "scenario",
    "run_id", "seed", "n_nodes", "SF", "packet_id", "packet_size_B",
    "transmitted_bytes", "energy_consumed", "tx_power_dBm", "coding_rate",
    "seq_seen_before",
}

METADATA_COLS = [
    "run_id", "scenario", "seed", "n_nodes", "SF",
    "window_start_s", "window_end_s", "Label",
]
DIAG_COLS = ["diag_D", "diag_C", "diag_duplicate_count"]

SCENARIO_MAP = {
    "NoAttack": "Normal", "Normal": "Normal",
    "Jamming": "Jamming", "Replay": "Replay", "Wormhole": "Wormhole",
}


def fnum(x, default=None):
    if x is None:
        return default
    s = str(x).strip()
    if s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def mean_std(values):
    if not values:
        return math.nan, math.nan
    m = statistics.fmean(values)
    if len(values) < 2:
        return m, math.nan
    return m, statistics.stdev(values)


def parse_run_filename(stem: str):
    m = re.match(r"^(NoAttack|Jamming|Replay|Wormhole)(20|30|50)?_sf(\d+)_s(\d+)$", stem)
    if not m:
        raise ValueError(f"Nom raw non reconnu: {stem}")
    cfg, nsize, sf, seed = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
    n_nodes = int(nsize) if nsize else 10
    return SCENARIO_MAP[cfg], seed, n_nodes, sf


def parse_sim_limit(log_path: Path, fallback: float) -> float:
    if log_path.exists():
        m = re.search(r"Simulation time limit reached -- at t=([0-9.]+)s", log_path.read_text(errors="replace"))
        if m:
            return float(m.group(1))
    return fallback


def scheduled_label(scenario: str, t0: float, t1: float) -> str:
    if scenario == "Normal":
        return "Normal"
    eps = 1e-9
    if t1 <= ATTACK_START_S + eps or t0 >= ATTACK_END_S - eps:
        return "Normal"
    if t0 >= ATTACK_START_S - eps and t1 <= ATTACK_END_S + eps:
        return scenario
    raise ValueError(f"Fenetre mixte {scenario} [{t0},{t1})")


def classify_raw_row(row: dict) -> str:
    received = fnum(row.get("received"), 0.0) or 0.0
    collision = fnum(row.get("collision"), 0.0) or 0.0
    if received >= 1.0:
        return "decoded"
    if collision >= 1.0:
        return "collision_gw"
    if received == 0.0:
        return "omniscient_tx"
    return "other"


def load_raw_csv(path: Path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def assert_x_no_leakage(feature_names):
    leaked = [c for c in feature_names if c in FORBIDDEN_IN_X]
    if leaked:
        raise SystemExit(f"LEAKAGE CHECK FAILED: {leaked}")
    extra = [c for c in feature_names if c not in FEATURES_X]
    if extra:
        raise SystemExit(f"LEAKAGE CHECK FAILED extra: {extra}")
    if list(feature_names) != FEATURES_X:
        raise SystemExit("LEAKAGE CHECK FAILED: X != FEATURES_X")


def process_run(csv_path: Path, log_path: Path) -> tuple[list[dict], dict]:
    stem = csv_path.stem
    scenario, seed, n_nodes, sf_file = parse_run_filename(stem)
    rows = load_raw_csv(csv_path)
    counts = {"raw_total": len(rows), "decoded": 0, "collision_gw": 0, "omniscient_tx": 0, "other": 0}
    decoded, collisions = [], []
    for row in rows:
        kind = classify_raw_row(row)
        counts[kind] = counts.get(kind, 0) + 1
        t = fnum(row.get("recv_time_s"))
        if t is None:
            continue
        if kind == "decoded":
            decoded.append(row)
        elif kind == "collision_gw":
            collisions.append(row)

    sim_end = parse_sim_limit(log_path, 1800.0)
    sfs = [int(fnum(r.get("spreading_factor"))) for r in decoded if fnum(r.get("spreading_factor")) is not None]
    sf_meta = sf_file if sf_file is not None else (max(set(sfs), key=sfs.count) if sfs else 12)
    run_id = f"{scenario}_n{n_nodes}_sf{sf_meta}_seed{seed}"

    first_rx = {}
    rx_count = defaultdict(int)
    decoded_sorted = sorted(decoded, key=lambda r: fnum(r["recv_time_s"]))
    dup_events = []
    for row in decoded_sorted:
        mac = (row.get("sender_mac") or "").strip()
        seq_s = "" if row.get("sequence_number") is None else str(row.get("sequence_number")).strip()
        t = fnum(row["recv_time_s"])
        if not mac or seq_s == "":
            continue
        key = (mac, seq_s)
        rx_count[key] += 1
        if key not in first_rx:
            first_rx[key] = t
        elif rx_count[key] >= 2:
            dup_events.append((t, t - first_rx[key], key))

    n_windows = int(math.floor(sim_end / WINDOW_S + 1e-12))
    windows = []
    for i in range(n_windows):
        t0 = i * WINDOW_S
        t1 = t0 + WINDOW_S
        label = scheduled_label(scenario, t0, t1)
        D_rows = [r for r in decoded if t0 <= fnum(r["recv_time_s"]) < t1]
        C_rows = [r for r in collisions if t0 <= fnum(r["recv_time_s"]) < t1]
        D, C = len(D_rows), len(C_rows)
        delays = [d for (t, d, _k) in dup_events if t0 <= t < t1]
        duplicate_count = len(delays)
        packet_rate = D / WINDOW_S
        collision_intensity = C / WINDOW_S
        if D + C == 0:
            gw_success_rate = collision_rate = math.nan
        else:
            gw_success_rate = D / (D + C)
            collision_rate = C / (D + C)
        duplicate_rate = math.nan if D == 0 else duplicate_count / D
        if delays:
            mean_d, min_d, max_d = statistics.fmean(delays), min(delays), max(delays)
        else:
            mean_d = min_d = max_d = math.nan
        rssis = [fnum(r.get("rssi_dBm")) for r in D_rows if fnum(r.get("rssi_dBm")) is not None]
        snirs = [fnum(r.get("snir_dB")) for r in D_rows if fnum(r.get("snir_dB")) is not None]
        mean_rssi, std_rssi = mean_std(rssis)
        mean_snir, std_snir = mean_std(snirs)
        times = sorted(fnum(r["recv_time_s"]) for r in D_rows)
        gaps = [times[j] - times[j - 1] for j in range(1, len(times))]
        if not gaps:
            ia_mean, ia_std = math.nan, math.nan
        else:
            ia_mean = statistics.fmean(gaps)
            ia_std = statistics.stdev(gaps) if len(gaps) >= 2 else math.nan
        windows.append({
            "run_id": run_id, "scenario": scenario, "seed": seed, "n_nodes": n_nodes, "SF": sf_meta,
            "window_start_s": t0, "window_end_s": t1, "Label": label,
            "diag_D": D, "diag_C": C, "diag_duplicate_count": duplicate_count,
            "packet_rate": packet_rate, "gw_success_rate": gw_success_rate,
            "collision_rate": collision_rate, "collision_intensity": collision_intensity,
            "duplicate_rate": duplicate_rate, "mean_duplicate_delay_s": mean_d,
            "min_duplicate_delay_s": min_d, "max_duplicate_delay_s": max_d,
            "mean_rssi": mean_rssi, "std_rssi": std_rssi, "mean_snir": mean_snir, "std_snir": std_snir,
            "interarrival_mean": ia_mean, "interarrival_std": ia_std,
        })
    counts["windows"] = len(windows)
    counts["sim_end_s"] = sim_end
    counts["run_id"] = run_id
    counts["scenario"] = scenario
    counts["seed"] = seed
    counts["n_nodes"] = n_nodes
    counts["dup_events_run"] = len(dup_events)
    counts["dup_runs_flag"] = 1 if dup_events else 0
    return windows, counts


def nanmean(xs):
    v = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.fmean(v) if v else math.nan


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {}
            for k in fieldnames:
                v = r.get(k)
                out[k] = "" if isinstance(v, float) and math.isnan(v) else v
            w.writerow(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-csv", type=Path, default=FEATURES_DIR / "dataset_v3_10nodes.csv")
    parser.add_argument("--only-n-nodes", type=int, default=10)
    parser.add_argument("--report-name", type=str, default="dataset_v3_10nodes_report.txt")
    args = parser.parse_args()

    csvs = sorted(p for p in args.raw_dir.glob("*.csv") if not p.name.endswith(".meta.csv"))
    if not csvs:
        raise SystemExit(f"Aucun CSV dans {args.raw_dir}")

    all_windows, all_counts = [], []
    for csv_path in csvs:
        try:
            scenario, seed, n_nodes, _sf = parse_run_filename(csv_path.stem)
        except ValueError:
            continue
        if n_nodes != args.only_n_nodes:
            continue
        windows, counts = process_run(csv_path, csv_path.with_suffix(".log"))
        counts["file"] = csv_path.name
        all_counts.append(counts)
        all_windows.extend(windows)

    assert_x_no_leakage(FEATURES_X)
    fieldnames = METADATA_COLS + DIAG_COLS + FEATURES_X
    write_csv(args.out_csv, all_windows, fieldnames)

    tot_raw = sum(c["raw_total"] for c in all_counts)
    tot_d = sum(c["decoded"] for c in all_counts)
    tot_c = sum(c["collision_gw"] for c in all_counts)
    tot_o = sum(c["omniscient_tx"] for c in all_counts)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "=== DATASET V3 ===",
        f"W={WINDOW_S}s attack=[{ATTACK_START_S},{ATTACK_END_S}) n={args.only_n_nodes}",
        f"runs={len(all_counts)} windows={len(all_windows)} expected_windows={len(all_counts)*EXPECTED_WINDOWS}",
        f"raw_total={tot_raw} D={tot_d} C={tot_c} omni={tot_o}",
        f"out={args.out_csv}",
    ]
    labels = defaultdict(int)
    for r in all_windows:
        labels[r["Label"]] += 1
    lines.append("labels=" + json.dumps(dict(labels)))
    report_path = REPORTS_DIR / args.report_name
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPORTS_DIR / args.report_name.replace(".txt", "_counts.json")).write_text(
        json.dumps({
            "raw_total": tot_raw, "decoded_used": tot_d, "collision_gw_used": tot_c,
            "omniscient_excluded": tot_o, "windows": len(all_windows), "runs": all_counts,
            "labels": dict(labels), "features_x": FEATURES_X,
        }, indent=2),
        encoding="utf-8",
    )
    print("\n".join(lines))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
