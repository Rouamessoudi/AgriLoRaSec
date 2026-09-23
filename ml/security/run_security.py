#!/usr/bin/env python3
"""Experiences securite avant/apres. N'ecrit pas dans ml/v2 ni ml/v3."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/home/opp_env/AgriLoRaSec")
SIM = ROOT / "simulations"
BIN = ROOT / "out/clang-release/src/AgriLoRaSec"
SEC = ROOT / "ml" / "security"
RAW = SEC / "raw"
FEAT = SEC / "features"
REPORTS = SEC / "reports"
FIGURES = SEC / "figures"

NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]

V2_CHECK = [
    ROOT / "ml/v2/features/dataset_v2_10nodes.csv",
    ROOT / "ml/v3/features/dataset_v3_10nodes.csv",
    ROOT / "ml/v3/ml/reports/scalability_table.csv",
    ROOT / "ml/v3/ml/reports/macro_f1_vs_nodes.png",
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


def parse_packet_csv(path: Path) -> dict:
    out = {
        "tx": 0,
        "rx": 0,
        "collision": 0,
        "seq_seen_before": 0,
        "legit_tx": 0,
        "legit_rx": 0,
    }
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            sender = (row.get("sender_name") or "").strip()
            rec = row.get("received", "").strip()
            coll = row.get("collision", "").strip()
            seen = row.get("seq_seen_before", "").strip()
            if coll == "1":
                out["collision"] += 1
            if rec == "1":
                out["rx"] += 1
                if seen == "1":
                    out["seq_seen_before"] += 1
                if sender.startswith("loRaNode"):
                    out["legit_rx"] += 1
                    if seen != "1":
                        out["unique_legit_rx"] = out.get("unique_legit_rx", 0) + 1
            elif rec == "0":
                out["tx"] += 1
                if sender.startswith("loRaNode"):
                    out["legit_lost_rows"] = out.get("legit_lost_rows", 0) + 1
    out["unique_legit_rx"] = out.get("unique_legit_rx", 0)
    out["legit_lost_rows"] = out.get("legit_lost_rows", 0)
    out["legit_tx"] = out["unique_legit_rx"] + out["legit_lost_rows"]
    out["pdr"] = (out["unique_legit_rx"] / out["legit_tx"]) if out["legit_tx"] else 0.0
    out["lost"] = out["legit_lost_rows"]
    return out


def parse_security_csv(path: Path) -> dict:
    out = {"accept": 0, "detect": 0, "reject": 0}
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            a = (row.get("action") or "").strip()
            if a in out:
                out[a] += 1
    return out


def count_log(text: str, needle: str) -> int:
    return sum(1 for ln in text.splitlines() if needle in ln)


def run_cfg(cfg, sim_time, seed=0, extra=None):
    RAW.mkdir(parents=True, exist_ok=True)
    log_path = RAW / f"{cfg}_s{seed}.log"
    cmd = [
        str(BIN), "-u", "Cmdenv", "-c", cfg, f"--seed-set={seed}",
        f"--sim-time-limit={sim_time}",
        "--cmdenv-express-mode=true",
        "--**.vector-recording=false",
        f"--output-scalar-file=results/sec_{cfg}_s{seed}.sca",
        f"--output-vector-file=results/sec_{cfg}_s{seed}.vec",
        "-n", NED, *LIBS,
    ]
    if extra:
        cmd.extend(extra)
    p = subprocess.run(cmd, cwd=str(SIM), capture_output=True, text=True)
    text = (p.stdout or "") + "\n" + (p.stderr or "")
    log_path.write_text(text, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(f"FAIL {cfg} rc={p.returncode}")
        print(text[-5000:])
        raise SystemExit(p.returncode)

    dest_pkt = RAW / f"{cfg}_s{seed}_packet_events.csv"
    dest_sec = RAW / f"{cfg}_s{seed}_security_events.csv"
    src_pkt = SIM / "results" / "packet_events.csv"
    src_sec = SIM / "results" / "security_events.csv"
    if src_pkt.is_file():
        shutil.copy2(src_pkt, dest_pkt)
    if src_sec.is_file():
        shutil.copy2(src_sec, dest_sec)

    pkt = parse_packet_csv(dest_pkt)
    sec = parse_security_csv(dest_sec)
    metrics = {
        "config": cfg,
        "seed": seed,
        "sim_time": sim_time,
        "exit_ok": True,
        **pkt,
        **{f"sec_{k}": v for k, v in sec.items()},
        "replay_tx": count_log(text, "ReplayApp REPLAY "),
        "replay_capture": count_log(text, "ReplayApp CAPTURE "),
        "wormhole_exit": count_log(text, "WormholeApp EXIT TX "),
        "wormhole_capture": count_log(text, "WormholeApp CAPTURE "),
        "jammer_send": count_log(text, "JammerApp SEND "),
        "channel_hop": count_log(text, "CHANNEL_HOP applied"),
        "gw_dup_reject": count_log(text, "GW_DUP_REJECT "),
    }
    return metrics


def write_table(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def comparison_rows(by_cfg: dict) -> list[dict]:
    pairs = [
        ("Jamming", "JammingProtected", "Jamming"),
        ("Replay", "ReplayProtected", "Replay"),
        ("Wormhole", "WormholeProtected", "Wormhole"),
    ]
    metrics = [
        ("legit_tx", "Paquets legitimes envoyes (approx TX non recus + recus)"),
        ("unique_legit_rx", "Receptions uniques legitimes (1er MAC,seq)"),
        ("legit_rx", "Receptions PHY sender loRaNode (incl. doublons)"),
        ("lost", "Paquets legitimes perdus (tx-rx)"),
        ("pdr", "Taux de reception legitime"),
        ("collision", "Collisions GW loggees"),
        ("seq_seen_before", "Receptions seq deja vue (PHY)"),
        ("sec_detect", "Doublons detectes (MAC,seq)"),
        ("sec_reject", "Doublons rejetes"),
        ("gw_dup_reject", "Rejets GW (log)"),
        ("replay_tx", "Replay retransmis"),
        ("wormhole_exit", "Wormhole EXIT TX"),
        ("channel_hop", "Noeuds ayant hoppe"),
    ]
    out = []
    for a, b, name in pairs:
        if a not in by_cfg or b not in by_cfg:
            continue
        wa, wb = by_cfg[a], by_cfg[b]
        for key, label in metrics:
            va, vb = wa.get(key, 0), wb.get(key, 0)
            try:
                diff = float(vb) - float(va)
            except (TypeError, ValueError):
                diff = ""
            out.append({
                "Attack": name,
                "Metric": label,
                "Without protection": va,
                "With protection": vb,
                "Difference": diff,
                "key": key,
            })
    return out


def make_figures(by_cfg: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    def bar2(title, fname, key, ylabel):
        labels, a, b = [], [], []
        for name, c0, c1 in [
            ("Jamming", "Jamming", "JammingProtected"),
            ("Replay", "Replay", "ReplayProtected"),
            ("Wormhole", "Wormhole", "WormholeProtected"),
        ]:
            if c0 in by_cfg and c1 in by_cfg:
                labels.append(name)
                a.append(float(by_cfg[c0].get(key, 0)))
                b.append(float(by_cfg[c1].get(key, 0)))
        if not labels:
            return
        x = range(len(labels))
        w = 0.35
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.bar([i - w / 2 for i in x], a, w, label="Sans protection", color="#b0b0b0")
        ax.bar([i + w / 2 for i in x], b, w, label="Avec protection", color="#2a6f97")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        fig.savefig(outdir / fname, dpi=150)
        plt.close(fig)

    bar2("Taux de reception unique legitime", "pdr_before_after.png", "pdr", "PDR unique")
    bar2("Collisions a la gateway", "collisions_before_after.png", "collision", "Nombre")
    bar2("Doublons rejetes (MAC, seq)", "duplicates_rejected.png", "sec_reject", "Nombre")

    # Replay blocking rate
    if "Replay" in by_cfg and "ReplayProtected" in by_cfg:
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        names = ["Retransmis", "Detectes", "Rejetes"]
        prot = by_cfg["ReplayProtected"]
        vals = [prot.get("replay_tx", 0), prot.get("sec_detect", 0), prot.get("sec_reject", 0)]
        ax.bar(names, vals, color=["#6c757d", "#e9c46a", "#2a6f97"])
        ax.set_title("Replay avec protection")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        fig.savefig(outdir / "replay_block.png", dpi=150)
        plt.close(fig)

    if "Wormhole" in by_cfg and "WormholeProtected" in by_cfg:
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        names = ["EXIT TX", "Detectes", "Rejetes"]
        prot = by_cfg["WormholeProtected"]
        vals = [prot.get("wormhole_exit", 0), prot.get("sec_detect", 0), prot.get("sec_reject", 0)]
        ax.bar(names, vals, color=["#6c757d", "#e9c46a", "#2a6f97"])
        ax.set_title("Wormhole avec protection (doublons)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        fig.savefig(outdir / "wormhole_block.png", dpi=150)
        plt.close(fig)


def main():
    before = {str(p): md5(p) for p in V2_CHECK}
    for d in (RAW, FEAT, REPORTS, FIGURES):
        d.mkdir(parents=True, exist_ok=True)

    phase = "smoke"
    if len(__import__("sys").argv) > 1:
        phase = __import__("sys").argv[1]

    if phase == "smoke":
        cfgs = [
            "SmokeNoAttackProtected",
            "SmokeJamming",
            "SmokeJammingProtected",
            "SmokeReplay",
            "SmokeReplayProtected",
            "SmokeWormhole",
            "SmokeWormholeProtected",
        ]
        sim_time = "120s"
        extra = []
        alias = {
            "SmokeJamming": "Jamming",
            "SmokeJammingProtected": "JammingProtected",
            "SmokeReplay": "Replay",
            "SmokeReplayProtected": "ReplayProtected",
            "SmokeWormhole": "Wormhole",
            "SmokeWormholeProtected": "WormholeProtected",
            "SmokeNoAttackProtected": "NoAttackProtected",
        }
    else:
        cfgs = [
            "SmokeNoAttackProtected",
            "SmokeJamming",
            "SmokeJammingProtected",
            "SmokeReplay",
            "SmokeReplayProtected",
            "SmokeWormhole",
            "SmokeWormholeProtected",
        ]
        sim_time = "400s"
        extra = [
            "--**.jammer.app[0].attackEnd=380s",
            "--**.replayer.app[0].attackEnd=380s",
            "--**.wormholeA.app[0].attackEnd=380s",
            "--**.wormholeB.app[0].attackEnd=380s",
        ]
        alias = {
            "SmokeJamming": "Jamming",
            "SmokeJammingProtected": "JammingProtected",
            "SmokeReplay": "Replay",
            "SmokeReplayProtected": "ReplayProtected",
            "SmokeWormhole": "Wormhole",
            "SmokeWormholeProtected": "WormholeProtected",
            "SmokeNoAttackProtected": "NoAttackProtected",
        }

    rows = []
    by_cfg = {}
    for cfg in cfgs:
        print(f"RUN {cfg} {sim_time}", flush=True)
        m = run_cfg(cfg, sim_time, seed=0, extra=extra)
        rows.append(m)
        by_cfg[alias.get(cfg, cfg)] = m
        print(
            f"  legit_rx={m['legit_rx']} legit_tx={m['legit_tx']} pdr={m['pdr']:.3f} "
            f"coll={m['collision']} reject={m.get('sec_reject', 0)} hop={m['channel_hop']}",
            flush=True,
        )

    write_table(rows, FEAT / f"metrics_{phase}.csv")
    cmp_rows = comparison_rows(by_cfg)
    write_table(cmp_rows, FEAT / f"comparison_{phase}.csv")
    make_figures(by_cfg, FIGURES)
    (REPORTS / f"metrics_{phase}.json").write_text(json.dumps(by_cfg, indent=2), encoding="utf-8")

    after = {str(p): md5(p) for p in V2_CHECK}
    intact = before == after
    (REPORTS / f"v2_v3_intact_{phase}.json").write_text(
        json.dumps({"intact": intact, "before": before, "after": after}, indent=2),
        encoding="utf-8",
    )
    print("V2/V3 intact:", intact)
    print("DONE", phase)


if __name__ == "__main__":
    main()
