#!/usr/bin/env python3
"""Pipeline dataset_v2 : fenetres temporelles 60s, observations GW uniquement.

Ne touche pas ml/dataset.csv, ml/dataset_20nodes.csv, ni les attaques.
"""
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
    "sender_name",
    "sender_mac",
    "sequence_number",
    "Label",
    "scenario",
    "run_id",
    "seed",
    "n_nodes",
    "SF",
    "packet_id",
    "packet_size_B",
    "transmitted_bytes",
    "energy_consumed",
    "tx_power_dBm",
    "coding_rate",
    "seq_seen_before",
}

METADATA_COLS = [
    "run_id",
    "scenario",
    "seed",
    "n_nodes",
    "SF",
    "window_start_s",
    "window_end_s",
    "activation_s",
    "Label",
]

DIAG_COLS = ["diag_D", "diag_C", "diag_duplicate_count"]

SCENARIO_MAP = {
    "NoAttack": "Normal",
    "Normal": "Normal",
    "Jamming": "Jamming",
    "Replay": "Replay",
    "Wormhole": "Wormhole",
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
    """Jamming_sf7_s0, Replay30_sf12_s3 ; ancien: Jamming20_s1."""
    m = re.match(r"^(NoAttack|Jamming|Replay|Wormhole)(20|30|50)?_sf(\d+)_s(\d+)$", stem)
    if m:
        cfg, nsize, sf, seed = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        n_nodes = int(nsize) if nsize else 10
        return SCENARIO_MAP[cfg], seed, n_nodes, sf
    m = re.match(r"^(NoAttack|Jamming|Replay|Wormhole)(20|30|50)?_s(\d+)$", stem)
    if not m:
        raise ValueError(f"Nom raw non reconnu: {stem}")
    cfg, nsize, seed = m.group(1), m.group(2), int(m.group(3))
    n_nodes = int(nsize) if nsize else 10
    return SCENARIO_MAP[cfg], seed, n_nodes, None


def parse_activation(log_path: Path, scenario: str) -> float:
    if not log_path.exists():
        if scenario == "Normal":
            return 0.0
        raise FileNotFoundError(f"Log requis pour activation {scenario}: {log_path}")
    text = log_path.read_text(errors="replace")
    if scenario == "Normal":
        return 0.0
    if scenario == "Jamming":
        m = re.search(r"JammerApp SEND #1 t=([0-9.]+)", text)
        return float(m.group(1)) if m else 1.0
    if scenario == "Replay":
        m = re.search(r"ReplayApp CAPTURE .* t=([0-9.eE+-]+)", text)
        if not m:
            m = re.search(r"ReplayApp DELAY drawn=.*capture_t=([0-9.eE+-]+)", text)
        if not m:
            return 5.0
        return float(m.group(1))
    if scenario == "Wormhole":
        m = re.search(r"WormholeApp DELAY drawn=.*capture_t=([0-9.eE+-]+)", text)
        if not m:
            m = re.search(r"WormholeApp CAPTURE .* t=([0-9.eE+-]+)", text)
        if not m:
            return 5.0
        return float(m.group(1))
    raise ValueError(scenario)


def parse_sim_limit(log_path: Path, fallback: float) -> float:
    if log_path.exists():
        m = re.search(r"Simulation time limit reached -- at t=([0-9.]+)s", log_path.read_text(errors="replace"))
        if m:
            return float(m.group(1))
    return fallback


def classify_raw_row(row: dict) -> str:
    """decoded | collision_gw | omniscient_tx | other"""
    received = fnum(row.get("received"), 0.0) or 0.0
    collision = fnum(row.get("collision"), 0.0) or 0.0
    mac = (row.get("sender_mac") or "").strip()
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
        raise SystemExit(f"LEAKAGE CHECK FAILED: colonnes interdites dans X: {leaked}")
    extra_forbidden = [c for c in feature_names if c not in FEATURES_X]
    if extra_forbidden:
        raise SystemExit(f"LEAKAGE CHECK FAILED: X contient des colonnes non autorisees: {extra_forbidden}")
    if list(feature_names) != FEATURES_X:
        raise SystemExit(f"LEAKAGE CHECK FAILED: X != FEATURES_X exactes.\nX={list(feature_names)}\nAttendu={FEATURES_X}")


def process_run(csv_path: Path, log_path: Path) -> tuple[list[dict], dict]:
    stem = csv_path.stem
    scenario, seed, n_nodes, sf_file = parse_run_filename(stem)
    rows = load_raw_csv(csv_path)
    counts = {"raw_total": len(rows), "decoded": 0, "collision_gw": 0, "omniscient_tx": 0, "other": 0}
    decoded = []
    collisions = []
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

    max_t = 0.0
    for row in decoded + collisions:
        max_t = max(max_t, fnum(row.get("recv_time_s"), 0.0) or 0.0)
    sim_end = parse_sim_limit(log_path, max(max_t, WINDOW_S))
    activation = parse_activation(log_path, scenario)

    sfs = []
    for row in decoded:
        sf = fnum(row.get("spreading_factor"))
        if sf is not None:
            sfs.append(int(sf))
    sf_meta = sf_file if sf_file is not None else (max(set(sfs), key=sfs.count) if sfs else 12)

    run_id = f"{scenario}_n{n_nodes}_sf{sf_meta}_seed{seed}"

    # Run-level duplicate memory: first decoded RX of (mac, seq)
    first_rx = {}
    rx_count = defaultdict(int)
    decoded_sorted = sorted(decoded, key=lambda r: fnum(r["recv_time_s"]))
    dup_events = []  # (t_copy, delay) for copies (2nd+ RX)
    for row in decoded_sorted:
        mac = (row.get("sender_mac") or "").strip()
        seq = row.get("sequence_number")
        seq_s = "" if seq is None else str(seq).strip()
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
    excluded_pre = 0
    for i in range(n_windows):
        t0 = i * WINDOW_S
        t1 = t0 + WINDOW_S
        if t1 <= activation:
            excluded_pre += 1
            continue

        D_rows = [r for r in decoded if t0 <= fnum(r["recv_time_s"]) < t1]
        C_rows = [r for r in collisions if t0 <= fnum(r["recv_time_s"]) < t1]
        D = len(D_rows)
        C = len(C_rows)

        delays = [d for (t, d, _k) in dup_events if t0 <= t < t1]
        duplicate_count = len(delays)

        packet_rate = D / WINDOW_S
        collision_intensity = C / WINDOW_S
        if D + C == 0:
            gw_success_rate = math.nan
            collision_rate = math.nan
        else:
            gw_success_rate = D / (D + C)
            collision_rate = C / (D + C)
        duplicate_rate = math.nan if D == 0 else duplicate_count / D
        if delays:
            mean_d = statistics.fmean(delays)
            min_d = min(delays)
            max_d = max(delays)
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

        rec = {
            "run_id": run_id,
            "scenario": scenario,
            "seed": seed,
            "n_nodes": n_nodes,
            "SF": sf_meta,
            "window_start_s": t0,
            "window_end_s": t1,
            "activation_s": activation,
            "Label": scenario,
            "diag_D": D,
            "diag_C": C,
            "diag_duplicate_count": duplicate_count,
            "packet_rate": packet_rate,
            "gw_success_rate": gw_success_rate,
            "collision_rate": collision_rate,
            "collision_intensity": collision_intensity,
            "duplicate_rate": duplicate_rate,
            "mean_duplicate_delay_s": mean_d,
            "min_duplicate_delay_s": min_d,
            "max_duplicate_delay_s": max_d,
            "mean_rssi": mean_rssi,
            "std_rssi": std_rssi,
            "mean_snir": mean_snir,
            "std_snir": std_snir,
            "interarrival_mean": ia_mean,
            "interarrival_std": ia_std,
        }
        windows.append(rec)

    counts["windows"] = len(windows)
    counts["excluded_pre_activation"] = excluded_pre
    counts["activation_s"] = activation
    counts["sim_end_s"] = sim_end
    counts["run_id"] = run_id
    counts["scenario"] = scenario
    counts["seed"] = seed
    counts["n_nodes"] = n_nodes
    counts["dup_events_run"] = len(dup_events)
    return windows, counts


def nanmean(xs):
    v = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.fmean(v) if v else math.nan


def nanmedian(xs):
    v = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.median(v) if v else math.nan


def nanstd(xs):
    v = [x for x in xs if x is not None and not math.isnan(x)]
    if len(v) < 2:
        return math.nan
    return statistics.stdev(v)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {}
            for k in fieldnames:
                v = r.get(k)
                if isinstance(v, float) and math.isnan(v):
                    out[k] = ""
                else:
                    out[k] = v
            w.writerow(out)


def pick_example(rows, pred, label):
    for r in rows:
        if pred(r):
            return r
    return None


def leakage_separation(rows: list[dict]) -> list[str]:
    """Signale des artefacts (pas d'optimisation ML)."""
    notes = []
    by = defaultdict(list)
    for r in rows:
        by[r["Label"]].append(r)

    # packet_rate Jamming vs others
    def vals(lab, feat):
        return [r[feat] for r in by.get(lab, []) if not math.isnan(r[feat])]

    jam = vals("Jamming", "packet_rate")
    oth = []
    for lab in ("Normal", "Replay", "Wormhole"):
        oth.extend(vals(lab, "packet_rate"))
    if jam and oth:
        jmin, jmax = min(jam), max(jam)
        omin, omax = min(oth), max(oth)
        if jmin > omax:
            notes.append(
                f"ARTEFACT packet_rate: min(Jamming)={jmin:.4f} > max(autres)={omax:.4f} "
                "(separe presque a lui seul le Jamming sur ce petit echantillon)."
            )
        elif omax > 0 and jmin > 2 * omax:
            notes.append(
                f"ARTEFACT possible packet_rate: Jamming [{jmin:.4f},{jmax:.4f}] "
                f"vs autres [{omin:.4f},{omax:.4f}]."
            )

    # duplicate delays Replay vs Wormhole
    rd = vals("Replay", "mean_duplicate_delay_s")
    wd = vals("Wormhole", "mean_duplicate_delay_s")
    if rd and wd:
        if max(wd) < min(rd):
            notes.append(
                f"ARTEFACT possible duplicate_delay: max(Wormhole)={max(wd):.3f} < "
                f"min(Replay)={min(rd):.3f} (peu de doublons recus; ne pas conclure a une separation parfaite)."
            )
    if rd and all(abs(x - 10.0) < 1e-6 for x in rd):
        notes.append("ARTEFACT: tous les delais Replay == 10s (constante-classe).")
    if wd and all(abs(x - 10.0) < 1e-6 for x in wd):
        notes.append("ARTEFACT: tous les delais Wormhole == 10s (constante-classe).")

    # RSSI almost constant per class
    for lab in by:
        rss = vals(lab, "mean_rssi")
        if len(rss) >= 2 and nanstd(rss) < 0.05:
            notes.append(f"mean_rssi presque constant pour {lab} (std={nanstd(rss):.4f}).")
    return notes


def fmt(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "NaN"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-csv", type=Path, default=FEATURES_DIR / "dataset_v2_validation_10nodes.csv")
    parser.add_argument("--only-n-nodes", type=int, default=10)
    parser.add_argument("--report-name", type=str, default="validation_10nodes_report.txt")
    args = parser.parse_args()

    raw_dir = args.raw_dir
    csvs = sorted(p for p in raw_dir.glob("*.csv") if not p.name.endswith(".meta.csv"))
    if not csvs:
        raise SystemExit(f"Aucun CSV dans {raw_dir}")

    all_windows = []
    all_counts = []
    for csv_path in csvs:
        try:
            scenario, seed, n_nodes, _sf = parse_run_filename(csv_path.stem)
        except ValueError:
            continue
        if n_nodes != args.only_n_nodes:
            continue
        log_path = csv_path.with_suffix(".log")
        windows, counts = process_run(csv_path, log_path)
        counts["file"] = csv_path.name
        all_counts.append(counts)
        all_windows.extend(windows)

    assert_x_no_leakage(FEATURES_X)
    fieldnames = METADATA_COLS + DIAG_COLS + FEATURES_X
    # Verifie qu'aucune colonne interdite n'est dans X (deja FEATURES_X)
    for c in FEATURES_X:
        if c in FORBIDDEN_IN_X or c in METADATA_COLS:
            raise SystemExit(f"LEAKAGE: {c}")

    write_csv(args.out_csv, all_windows, fieldnames)

    # Relecture + controle colonnes X du fichier
    with args.out_csv.open() as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
    x_in_file = [c for c in header if c in FEATURES_X]
    assert_x_no_leakage(x_in_file)
    leaked_header = [c for c in FEATURES_X if c in FORBIDDEN_IN_X]
    if leaked_header:
        raise SystemExit("LEAKAGE in header")
    extra = set(header) & FORBIDDEN_IN_X
    # Label, scenario, run_id, seed, n_nodes, SF sont metadonnees, pas X
    extra_in_x = extra & set(FEATURES_X)
    if extra_in_x:
        raise SystemExit(f"LEAKAGE extra in X: {extra_in_x}")

    tot_raw = sum(c["raw_total"] for c in all_counts)
    tot_d = sum(c["decoded"] for c in all_counts)
    tot_c = sum(c["collision_gw"] for c in all_counts)
    tot_o = sum(c["omniscient_tx"] for c in all_counts)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    def p(s=""):
        lines.append(s)
        print(s)

    p("=== DATASET V2 VALIDATION PIPELINE ===")
    p(f"W={WINDOW_S}s  n_nodes={args.only_n_nodes}  runs={len(all_counts)}  windows={len(all_windows)}")
    p(f"out={args.out_csv}")
    p()
    p("--- raw filter ---")
    p(f"raw_total={tot_raw}")
    p(f"RX_GW_decoded_used={tot_d}")
    p(f"collision_GW_used={tot_c}")
    p(f"received0_omniscient_excluded={tot_o}")
    p()
    p("--- per run ---")
    for c in all_counts:
        p(
            f"{c['file']}: raw={c['raw_total']} D={c['decoded']} C={c['collision_gw']} "
            f"omni={c['omniscient_tx']} windows={c['windows']} excl_pre={c['excluded_pre_activation']} "
            f"act={c['activation_s']:.4f} dups_run={c['dup_events_run']}"
        )

    p()
    p("--- examples ---")
    examples = [
        ("A_Normal", lambda r: r["Label"] == "Normal"),
        ("B_Jamming", lambda r: r["Label"] == "Jamming"),
        ("C_Replay_no_dup", lambda r: r["Label"] == "Replay" and r["diag_duplicate_count"] == 0),
        ("D_Replay_dup", lambda r: r["Label"] == "Replay" and r["diag_duplicate_count"] > 0),
        ("E_Wormhole_no_dup", lambda r: r["Label"] == "Wormhole" and r["diag_duplicate_count"] == 0),
        ("F_Wormhole_dup", lambda r: r["Label"] == "Wormhole" and r["diag_duplicate_count"] > 0),
    ]
    for name, pred in examples:
        r = pick_example(all_windows, pred, name)
        p(f"[{name}]")
        if r is None:
            p("  ABSENT dans cet echantillon de validation")
            continue
        p(f"  run_id={r['run_id']} t=[{r['window_start_s']},{r['window_end_s']}) Label={r['Label']}")
        p(f"  D={r['diag_D']} C={r['diag_C']} duplicate_count={r['diag_duplicate_count']} activation_s={r['activation_s']}")
        for feat in FEATURES_X:
            p(f"  {feat}={fmt(r[feat])}")

    p()
    p("--- stats by class ---")
    by = defaultdict(list)
    for r in all_windows:
        by[r["Label"]].append(r)
    for lab in ("Normal", "Jamming", "Replay", "Wormhole"):
        rs = by.get(lab, [])
        p(f"## {lab} n_windows={len(rs)}")
        n_dup = sum(1 for r in rs if (not math.isnan(r["duplicate_rate"]) and r["duplicate_rate"] > 0))
        p(f"  windows_duplicate_rate>0 = {n_dup}")
        for feat in FEATURES_X:
            xs = [r[feat] for r in rs]
            n_nan = sum(1 for x in xs if math.isnan(x))
            p(
                f"  {feat}: mean={fmt(nanmean(xs))} median={fmt(nanmedian(xs))} "
                f"std={fmt(nanstd(xs))} nan={n_nan}/{len(xs)}"
            )
            finite = [x for x in xs if not math.isnan(x)]
            if finite and max(finite) - min(finite) < 1e-12:
                p(f"    NOTE: constante (= {fmt(finite[0])})")

    p()
    p("--- scientific checks ---")
    n_norm_dup = sum(1 for r in by["Normal"] if r["diag_duplicate_count"] > 0)
    p(f"Normal duplicate_count>0 windows: {n_norm_dup} (attendu 0)")
    jam_pr = [r["packet_rate"] for r in by["Jamming"]]
    p(f"Jamming packet_rate mean={fmt(nanmean(jam_pr))} (jammer ~0.57/s + capteurs)")
    jam_ci = [r["collision_intensity"] for r in by["Jamming"]]
    p(f"Jamming collision_intensity mean={fmt(nanmean(jam_ci))}")
    for lab in ("Replay", "Wormhole"):
        with_d = [r for r in by[lab] if r["diag_duplicate_count"] > 0]
        without = [r for r in by[lab] if r["diag_duplicate_count"] == 0]
        p(f"{lab}: windows_with_dup={len(with_d)} without_dup_but_label={len(without)}")
        for r in with_d:
            p(
                f"  dup {r['run_id']} W=[{r['window_start_s']},{r['window_end_s']}) "
                f"rate={fmt(r['duplicate_rate'])} delay={fmt(r['mean_duplicate_delay_s'])}"
            )

    p()
    p("--- leakage / artefacts ---")
    notes = leakage_separation(all_windows)
    if not notes:
        p("Pas de separation triviale complete detectee (echantillon petit).")
    for n in notes:
        p(n)
    p("Controle X: FEATURES_X exactes, aucune colonne interdite dans X: OK")

    report_path = REPORTS_DIR / args.report_name
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    counts_name = args.report_name.replace(".txt", "_counts.json")
    (REPORTS_DIR / counts_name).write_text(json.dumps({
        "raw_total": tot_raw,
        "decoded_used": tot_d,
        "collision_gw_used": tot_c,
        "omniscient_excluded": tot_o,
        "windows": len(all_windows),
        "runs": all_counts,
        "features_x": FEATURES_X,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {report_path}")


if __name__ == "__main__":
    main()
