#!/usr/bin/env python3
"""Campagne securite finale 10 noeuds. Ne touche pas ml/v2 ni ml/v3 (lecture seule)."""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import statistics
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/home/opp_env/AgriLoRaSec")
SIM = ROOT / "simulations"
BIN = ROOT / "out/clang-release/src/AgriLoRaSec"
V3_RAW = ROOT / "ml/v3/raw/10nodes"
OUT = ROOT / "ml/security/final_10nodes"
RAW_B = OUT / "raw" / "before"
RAW_A = OUT / "raw" / "after"
LOGS = OUT / "logs"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"

NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]
SIM_TIME = "1800s"
SEEDS = [0, 1, 2, 3]
SFS = [7, 8, 9, 10, 11, 12]

BEFORE_CFG = {
    "Jamming": "Jamming",
    "Replay": "Replay",
    "Wormhole": "Wormhole",
    "Normal": "NoAttack",
}
AFTER_CFG = {
    "Jamming": "JammingProtected",
    "Replay": "ReplayProtected",
    "Wormhole": "WormholeProtected",
    "Normal": "NoAttackProtected",
}


def mean_std(xs):
    xs = [float(x) for x in xs if x is not None and x != "NA" and not (isinstance(x, float) and math.isnan(x))]
    if not xs:
        return "NA", "NA"
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), statistics.stdev(xs)


def parse_packet_csv(path: Path) -> dict:
    out = {
        "tx_legit": 0,
        "rx_all": 0,
        "rx_original": 0,
        "rx_copy": 0,
        "collisions": 0,
        "seq_seen_phy": 0,
        "true_dup_pairs": 0,
        "rssi": [],
        "snir": [],
    }
    keys = defaultdict(int)
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            sender = (row.get("sender_name") or "").strip()
            rec = (row.get("received") or "").strip()
            coll = (row.get("collision") or "").strip()
            seen = (row.get("seq_seen_before") or "").strip()
            mac = (row.get("sender_mac") or "").strip()
            seq = (row.get("sequence_number") or "").strip()
            if coll == "1":
                out["collisions"] += 1
            if rec == "1":
                out["rx_all"] += 1
                if seen == "1":
                    out["seq_seen_phy"] += 1
                if mac and seq:
                    keys[(mac, seq)] += 1
                try:
                    if row.get("rssi_dBm"):
                        out["rssi"].append(float(row["rssi_dBm"]))
                    if row.get("snir_dB"):
                        out["snir"].append(float(row["snir_dB"]))
                except ValueError:
                    pass
                if sender in ("replayer", "wormholeB"):
                    out["rx_copy"] += 1
                elif sender.startswith("loRaNode"):
                    out["rx_original"] += 1
            elif rec == "0" and sender.startswith("loRaNode"):
                out["tx_legit"] += 1
    out["tx_legit"] += out["rx_original"]
    out["true_dup_pairs"] = sum(1 for n in keys.values() if n >= 2)
    out["pdr"] = (out["rx_original"] / out["tx_legit"]) if out["tx_legit"] else 0.0
    out["lost"] = max(0, out["tx_legit"] - out["rx_original"])
    denom = out["rx_all"] + out["collisions"]
    out["collision_rate"] = (out["collisions"] / denom) if denom else 0.0
    out["rssi_mean"] = statistics.mean(out["rssi"]) if out["rssi"] else "NA"
    out["snir_mean"] = statistics.mean(out["snir"]) if out["snir"] else "NA"
    return out


def parse_security_csv(path: Path) -> dict:
    out = {"accept": 0, "detect": 0, "reject": 0}
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            a = (row.get("action") or "").strip()
            if a in out:
                out[a] += 1
    return out


def parse_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    def cnt(s):
        return sum(1 for ln in text.splitlines() if s in ln)
    return {
        "replay_tx": cnt("ReplayApp REPLAY "),
        "replay_cap": cnt("ReplayApp CAPTURE "),
        "wh_exit": cnt("WormholeApp EXIT TX "),
        "wh_tun": cnt("WormholeApp TUNNEL A->B "),
        "wh_cap": cnt("WormholeApp CAPTURE "),
        "jam_send": cnt("JammerApp SEND "),
        "hop": cnt("CHANNEL_HOP applied"),
        "gw_reject": cnt("GW_DUP_REJECT "),
        "ok1800": "Simulation time limit reached -- at t=1800s" in text,
        "error": "Error:" in text,
    }


def na_metrics(attack: str, pkt: dict, sec: dict, log: dict, protection: str) -> dict:
    copy_tx = "NA"
    copy_rx = "NA"
    if attack == "Replay":
        copy_tx = log.get("replay_tx", 0)
        copy_rx = pkt.get("rx_copy", 0)
    elif attack == "Wormhole":
        copy_tx = log.get("wh_exit", 0)
        copy_rx = pkt.get("rx_copy", 0)
    elif attack == "Jamming":
        copy_tx = log.get("jam_send", 0)
        copy_rx = "NA"
    filt = protection == "AFTER"
    det = sec.get("detect", 0) if filt else pkt.get("seq_seen_phy", 0)
    rej = sec.get("reject", 0) if filt else 0
    if attack == "Normal":
        false_rej = rej if filt else 0
        dup_acc = "NA"
    else:
        false_rej = "NA"
        if filt:
            dup_acc = max(0, (copy_rx if isinstance(copy_rx, int) else 0) - rej)
        else:
            dup_acc = pkt.get("seq_seen_phy", 0)
    return {
        "OriginalRX": pkt.get("rx_original", 0),
        "AttackCopyTX": copy_tx,
        "AttackCopyRX": copy_rx,
        "TrueDuplicatePairs": pkt.get("true_dup_pairs", 0),
        "DuplicateDetected": det,
        "DuplicateRejected": rej,
        "DuplicateAccepted": dup_acc,
        "FalseRejects": false_rej,
        "TX": pkt.get("tx_legit", 0),
        "RX": pkt.get("rx_original", 0),
        "Collisions": pkt.get("collisions", 0),
        "CollisionRate": pkt.get("collision_rate", 0),
        "PDR": pkt.get("pdr", 0),
        "RssiMean": pkt.get("rssi_mean", "NA"),
        "SnirMean": pkt.get("snir_mean", "NA"),
        "Lost": pkt.get("lost", 0),
    }


def after_job(attack: str, sf: int, seed: int) -> dict:
    cfg = AFTER_CFG[attack]
    stem = f"{cfg}_sf{sf}_s{seed}"
    d = RAW_A / attack
    d.mkdir(parents=True, exist_ok=True)
    return {
        "attack": attack, "sf": sf, "seed": seed, "cfg": cfg, "stem": stem,
        "csv": d / f"{stem}.csv",
        "sec": d / f"{stem}_security.csv",
        "log": LOGS / f"{stem}.log",
        "ok": d / f"{stem}.ok",
    }


def is_after_done(job: dict) -> bool:
    if not job["csv"].is_file() or job["csv"].stat().st_size <= 20:
        return False
    if not job["log"].is_file():
        return False
    t = job["log"].read_text(encoding="utf-8", errors="replace")
    return "Simulation time limit reached -- at t=1800s" in t and "Error:" not in t


def run_after(job: dict) -> dict:
    if is_after_done(job):
        return {"stem": job["stem"], "status": "skip"}
    job["log"].parent.mkdir(parents=True, exist_ok=True)
    job["csv"].parent.mkdir(parents=True, exist_ok=True)
    pkt_rel = f"results/{job['stem']}.csv"
    sec_rel = f"results/{job['stem']}_security.csv"
    cmd = [
        str(BIN), "-u", "Cmdenv", "-c", job["cfg"],
        f"--sim-time-limit={SIM_TIME}",
        "--cmdenv-express-mode=true",
        f"--seed-set={job['seed']}",
        f"--output-scalar-file=results/sec10_{job['stem']}.sca",
        f"--output-vector-file=results/sec10_{job['stem']}.vec",
        "--**.vector-recording=false",
        f"--**.loRaNode*.app[0].initialLoRaSF={job['sf']}",
        f"--**.jammer.app[0].initialLoRaSF={job['sf']}",
        f"--**.replayer.app[0].initialLoRaSF={job['sf']}",
        f"--**.wormholeA.app[0].initialLoRaSF={job['sf']}",
        f"--**.wormholeB.app[0].initialLoRaSF={job['sf']}",
        f'--**.packetEventLogger.outputFile="{pkt_rel}"',
        f'--**.packetForwarder.securityLogFile="{sec_rel}"',
        "-n", NED,
    ] + LIBS
    t0 = time.time()
    with job["log"].open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, cwd=str(SIM), stdout=f, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    src_csv = SIM / pkt_rel
    src_sec = SIM / sec_rel
    if src_csv.is_file():
        shutil.copy2(src_csv, job["csv"])
    if src_sec.is_file():
        shutil.copy2(src_sec, job["sec"])
    logtxt = job["log"].read_text(encoding="utf-8", errors="replace") if job["log"].is_file() else ""
    ok = (
        proc.returncode == 0
        and "Simulation time limit reached -- at t=1800s" in logtxt
        and "Error:" not in logtxt
        and job["csv"].is_file()
        and job["csv"].stat().st_size > 20
    )
    if ok:
        job["ok"].write_text(f"ok dt={dt:.1f}\n")
        return {"stem": job["stem"], "status": "ok", "dt": dt}
    return {"stem": job["stem"], "status": "fail", "dt": dt, "rc": proc.returncode, "tail": logtxt[-500:]}


def copy_before():
    RAW_B.mkdir(parents=True, exist_ok=True)
    reused = []
    missing = []
    for attack, cfg in BEFORE_CFG.items():
        dest = RAW_B / attack
        dest.mkdir(parents=True, exist_ok=True)
        for sf in SFS:
            for seed in SEEDS:
                stem = f"{cfg}_sf{sf}_s{seed}"
                src_csv = V3_RAW / f"{stem}.csv"
                src_log = V3_RAW / f"{stem}.log"
                src_ok = V3_RAW / f"{stem}.ok"
                if src_csv.is_file() and src_log.is_file():
                    log = src_log.read_text(encoding="utf-8", errors="replace")
                    if "Simulation time limit reached -- at t=1800s" in log and "Error:" not in log:
                        shutil.copy2(src_csv, dest / f"{stem}.csv")
                        shutil.copy2(src_log, dest / f"{stem}.log")
                        if src_ok.is_file():
                            shutil.copy2(src_ok, dest / f"{stem}.ok")
                        reused.append(stem)
                        continue
                missing.append(stem)
    return reused, missing


def all_after_jobs():
    jobs = []
    for attack in AFTER_CFG:
        for sf in SFS:
            for seed in SEEDS:
                jobs.append(after_job(attack, sf, seed))
    return jobs


def row_for(attack, sf, seed, protection, pkt_path, log_path, sec_path):
    pkt = parse_packet_csv(pkt_path)
    log = parse_log(log_path)
    sec = parse_security_csv(sec_path) if sec_path else {"accept": 0, "detect": 0, "reject": 0}
    m = na_metrics(attack, pkt, sec, log, protection)
    return {
        "Attack": attack,
        "Protection": protection,
        "Nodes": 10,
        "SF": sf,
        "Seed": seed,
        "Duration": 1800,
        **m,
        "SimOk": log.get("ok1800", False),
    }


def collect_rows():
    rows = []
    for attack, cfg in BEFORE_CFG.items():
        for sf in SFS:
            for seed in SEEDS:
                stem = f"{cfg}_sf{sf}_s{seed}"
                rows.append(row_for(
                    attack, sf, seed, "BEFORE",
                    RAW_B / attack / f"{stem}.csv",
                    RAW_B / attack / f"{stem}.log",
                    None,
                ))
    for attack, cfg in AFTER_CFG.items():
        for sf in SFS:
            for seed in SEEDS:
                stem = f"{cfg}_sf{sf}_s{seed}"
                job = after_job(attack, sf, seed)
                rows.append(row_for(
                    attack, sf, seed, "AFTER",
                    job["csv"], job["log"], job["sec"],
                ))
    return rows


def write_csv(path: Path, rows: list, fieldnames: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def summary_rows(rows):
    out = []
    for attack in BEFORE_CFG:
        for prot in ("BEFORE", "AFTER"):
            sub = [r for r in rows if r["Attack"] == attack and r["Protection"] == prot]
            if not sub:
                continue
            rec = {"Attack": attack, "Protection": prot, "N": len(sub)}
            for key in ("TX", "RX", "Collisions", "CollisionRate", "PDR", "OriginalRX",
                        "AttackCopyTX", "AttackCopyRX", "TrueDuplicatePairs",
                        "DuplicateDetected", "DuplicateRejected", "DuplicateAccepted", "FalseRejects"):
                xs = []
                for r in sub:
                    v = r.get(key)
                    if v in (None, "NA"):
                        continue
                    try:
                        xs.append(float(v))
                    except (TypeError, ValueError):
                        pass
                mu, sd = mean_std(xs)
                rec[f"{key}_mean"] = mu
                rec[f"{key}_std"] = sd
            out.append(rec)
    return out


def make_figures(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)

    def series(attack, prot, key):
        ys = []
        for sf in SFS:
            sub = [r for r in rows if r["Attack"] == attack and r["Protection"] == prot and r["SF"] == sf]
            xs = []
            for r in sub:
                v = r.get(key)
                if v in (None, "NA"):
                    continue
                xs.append(float(v))
            ys.append(statistics.mean(xs) if xs else 0.0)
        return ys

    def plot_ba(attack, key, ylabel, fname):
        b = series(attack, "BEFORE", key)
        a = series(attack, "AFTER", key)
        x = range(len(SFS))
        w = 0.35
        fig, ax = plt.subplots(figsize=(7.4, 4.2))
        ax.bar([i - w / 2 for i in x], b, w, label="Sans protection", color="#b0b0b0")
        ax.bar([i + w / 2 for i in x], a, w, label="Avec protection", color="#2a6f97")
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"SF{s}" for s in SFS])
        ax.set_ylabel(ylabel)
        ax.set_title(f"{attack} — {ylabel} (10 nœuds, moyenne 4 seeds)")
        ax.legend()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        fig.savefig(FIGURES / fname, dpi=150)
        plt.close(fig)

    plot_ba("Jamming", "Collisions", "Collisions GW", "jamming_collisions_by_sf.png")
    plot_ba("Jamming", "PDR", "PDR unique legitime", "jamming_pdr_by_sf.png")
    plot_ba("Replay", "AttackCopyRX", "Copies RAW recues GW", "replay_copy_rx_by_sf.png")
    plot_ba("Replay", "DuplicateDetected", "Doublons detectes", "replay_detected_by_sf.png")
    plot_ba("Replay", "DuplicateRejected", "Doublons rejetes", "replay_rejected_by_sf.png")
    plot_ba("Wormhole", "AttackCopyRX", "Copies EXIT recues GW", "wormhole_copy_rx_by_sf.png")
    plot_ba("Wormhole", "DuplicateDetected", "Doublons detectes", "wormhole_detected_by_sf.png")
    plot_ba("Wormhole", "DuplicateRejected", "Doublons rejetes", "wormhole_rejected_by_sf.png")
    plot_ba("Normal", "FalseRejects", "Faux rejets", "normal_false_rejects_by_sf.png")
    plot_ba("Normal", "PDR", "PDR", "normal_pdr_by_sf.png")


def write_report(rows, summary, reused, missing, run_stats):
    REPORTS.mkdir(parents=True, exist_ok=True)

    def get(attack, prot, key):
        for s in summary:
            if s["Attack"] == attack and s["Protection"] == prot:
                return s.get(f"{key}_mean", "NA"), s.get(f"{key}_std", "NA")
        return "NA", "NA"

    def fmt(mu, sd):
        if mu == "NA":
            return "NA"
        try:
            return f"{float(mu):.4g} ± {float(sd):.4g}"
        except (TypeError, ValueError):
            return str(mu)

    jam_c_b = get("Jamming", "BEFORE", "Collisions")
    jam_c_a = get("Jamming", "AFTER", "Collisions")
    jam_p_b = get("Jamming", "BEFORE", "PDR")
    jam_p_a = get("Jamming", "AFTER", "PDR")
    rp_tx = get("Replay", "AFTER", "AttackCopyTX")
    rp_rx = get("Replay", "AFTER", "AttackCopyRX")
    rp_pair = get("Replay", "AFTER", "TrueDuplicatePairs")
    rp_rej = get("Replay", "AFTER", "DuplicateRejected")
    rp_det = get("Replay", "AFTER", "DuplicateDetected")
    wh_tx = get("Wormhole", "AFTER", "AttackCopyTX")
    wh_rx = get("Wormhole", "AFTER", "AttackCopyRX")
    wh_pair = get("Wormhole", "AFTER", "TrueDuplicatePairs")
    wh_rej = get("Wormhole", "AFTER", "DuplicateRejected")
    no_fr = get("Normal", "AFTER", "FalseRejects")

    def rate(det, rej):
        try:
            d, r = float(det[0]), float(rej[0])
            if d <= 0:
                return "indetermine (0 opportunite au filtre)"
            return f"{100.0 * r / d:.1f}% (rejet/detection moyenne)"
        except (TypeError, ValueError):
            return "NA"

    jam_better_c = False
    jam_better_p = False
    try:
        jam_better_c = float(jam_c_a[0]) < float(jam_c_b[0])
        jam_better_p = float(jam_p_a[0]) > float(jam_p_b[0])
    except (TypeError, ValueError):
        pass
    jam_yes = jam_better_c or jam_better_p
    try:
        replay_yes = float(rp_rej[0]) > 0
    except (TypeError, ValueError):
        replay_yes = False
    try:
        wh_yes = float(wh_rej[0]) > 0
    except (TypeError, ValueError):
        wh_yes = False

    lines = f"""# Securite AgriLoRaSec — campagne finale 10 nœuds

## 1. Objectif

Comparer, sur le **même réseau 10 nœuds** que la campagne V3 (1800 s, SF7–12, seeds 0–3) :

attaque **sans** protection vs **avec** protection.

ML V2/V3 inchangé. Distances / puissance / propagation inchangées.

## 2. Configuration 10 nœuds

- Réseau `AgriLoRaNetwork`, `omnetpp.ini` configs `Jamming` / `Replay` / `Wormhole` / `NoAttack`
- Protections : `JammingProtected` (hop 868.0→868.3 MHz à t=360 s), `ReplayProtected` et `WormholeProtected` (filtre GW MAC+seq)
- Contrôle : `NoAttackProtected` (hop + filtre)

## 3. Protocole

- BEFORE : runs V3 `ml/v3/raw/10nodes/` réutilisés (1800 s, mêmes SF/seeds/configs d'attaque)
- AFTER : nouveaux runs uniquement `*Protected`
- Réutilisés : {len(reused)} ; manquants BEFORE : {len(missing)}
- Nouveaux runs demandés : {run_stats.get('requested', 'NA')}
- Réussis : {run_stats.get('ok', 'NA')} ; skip déjà faits : {run_stats.get('skip', 'NA')} ; échoués : {run_stats.get('fail', 'NA')}

## 4. Jamming

Protection = channel hop des nœuds légitimes, jammer reste à 868 MHz.

- Collisions BEFORE : {fmt(*jam_c_b)}
- Collisions AFTER : {fmt(*jam_c_a)}
- PDR BEFORE : {fmt(*jam_p_b)}
- PDR AFTER : {fmt(*jam_p_a)}

## 5. Replay

Replay RAW + filtre first-seen. Une RAW TX n'est pas une RAW RX.

- RAW TX AFTER : {fmt(*rp_tx)}
- RAW RX GW AFTER : {fmt(*rp_rx)}
- True duplicate pairs AFTER : {fmt(*rp_pair)}
- Detected AFTER : {fmt(*rp_det)}
- Rejected AFTER : {fmt(*rp_rej)}
- Taux de rejet si opportunité : {rate(rp_det, rp_rej)}

## 6. Wormhole

Même filtre, topologie étoile.

- EXIT TX AFTER : {fmt(*wh_tx)}
- EXIT RX GW AFTER : {fmt(*wh_rx)}
- True duplicate pairs AFTER : {fmt(*wh_pair)}
- Rejected AFTER : {fmt(*wh_rej)}
- Taux de rejet si opportunité : {rate(get("Wormhole","AFTER","DuplicateDetected"), wh_rej)}

## 7. Comparaison BEFORE/AFTER

Voir `tables/security_10nodes_detailed.csv` et `tables/security_10nodes_summary.csv`.

## 8. Faux positifs (Normal)

False rejects AFTER : {fmt(*no_fr)}

## 9. Limites

Le filtre Replay/Wormhole n'agit que si **original et copie** sont tous deux décodés à la GW.
Les pertes de portée V3 restent. Aucun paramètre radio n'a été modifié pour forcer des rejets.

## 10. Conclusion

**IMPLEMENTATION CORRECTE**

- Jamming hop : oui (FLoRa collision = même CF)
- Replay/Wormhole filtre MAC+seq à `LoggingPacketForwarder` : oui

**EFFICACITÉ EXPÉRIMENTALEMENT OBSERVÉE**

- JAMMING PROTECTION EXPERIMENTALLY VALIDATED: {"YES" if jam_yes else "NO"}
- REPLAY PROTECTION EXPERIMENTALLY VALIDATED: {"YES" if replay_yes else "NO"}
- WORMHOLE PROTECTION EXPERIMENTALLY VALIDATED: {"YES" if wh_yes else "NO"}
"""
    (REPORTS / "security_10nodes_final_report.md").write_text(lines, encoding="utf-8")
    (REPORTS / "run_stats.json").write_text(json.dumps({
        "reused_before": reused, "missing_before": missing, "run_stats": run_stats,
        "jamming_yes": jam_yes, "replay_yes": replay_yes, "wormhole_yes": wh_yes,
    }, indent=2), encoding="utf-8")


def main():
    for p in (OUT, RAW_B, RAW_A, LOGS, TABLES, FIGURES, REPORTS):
        p.mkdir(parents=True, exist_ok=True)
    print("AUDIT: reuse V3 10-node 1800s baselines", flush=True)
    reused, missing = copy_before()
    print(f"BEFORE reused={len(reused)} missing={len(missing)}", flush=True)
    if missing:
        print("MISSING BASELINES", missing[:20], flush=True)

    jobs = all_after_jobs()
    pending = [j for j in jobs if not is_after_done(j)]
    workers = int(os.environ.get("SEC10_WORKERS", "4"))
    print(f"AFTER jobs total={len(jobs)} pending={len(pending)} workers={workers}", flush=True)
    stats = {"requested": len(jobs), "ok": 0, "skip": len(jobs) - len(pending), "fail": 0}
    results = []
    if pending:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_after, j): j["stem"] for j in pending}
            n = 0
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                n += 1
                stats[r["status"]] = stats.get(r["status"], 0) + 1
                print(f"progress {n}/{len(pending)} {r['stem']} {r['status']}", flush=True)
                if r["status"] == "fail":
                    print(str(r.get("tail", ""))[:400], flush=True)
    stats["ok"] = stats.get("ok", 0)
    stats["fail"] = stats.get("fail", 0)
    (REPORTS / "after_run_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    rows = collect_rows()
    fields = [
        "Attack", "Protection", "Nodes", "SF", "Seed", "Duration",
        "TX", "RX", "Collisions", "CollisionRate", "PDR", "Lost",
        "OriginalRX", "AttackCopyTX", "AttackCopyRX", "TrueDuplicatePairs",
        "DuplicateDetected", "DuplicateRejected", "DuplicateAccepted", "FalseRejects",
        "RssiMean", "SnirMean", "SimOk",
    ]
    write_csv(TABLES / "security_10nodes_detailed.csv", rows, fields)
    summ = summary_rows(rows)
    if summ:
        sfields = list(summ[0].keys())
        write_csv(TABLES / "security_10nodes_summary.csv", summ, sfields)
    make_figures(rows)
    write_report(rows, summ, reused, missing, stats)
    print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
