#!/usr/bin/env python3
from pathlib import Path
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/home/opp_env/AgriLoRaSec/ml/security")
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

rows = list(csv.DictReader((ROOT / "features/comparison_eval.csv").open(encoding="utf-8")))

def val(attack, key):
    for r in rows:
        if r["Attack"] == attack and r["key"] == key:
            return float(r["Without protection"]), float(r["With protection"])
    return None, None

def grouped(key, title, ylabel, fname):
    attacks = ["Jamming", "Replay", "Wormhole"]
    a, b = [], []
    labs = []
    for at in attacks:
        va, vb = val(at, key)
        if va is None:
            continue
        labs.append(at)
        a.append(va)
        b.append(vb)
    x = range(len(labs))
    w = 0.35
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar([i - w/2 for i in x], a, w, label="Sans protection", color="#b0b0b0")
    ax.bar([i + w/2 for i in x], b, w, label="Avec protection", color="#2a6f97")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labs)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150)
    plt.close(fig)

grouped("collision", "Collisions gateway (400 s, SF7)", "Nombre", "collisions_before_after.png")
grouped("pdr", "PDR unique legitime (400 s, SF7)", "PDR", "pdr_before_after.png")
grouped("sec_reject", "Doublons rejetes (MAC, seq)", "Nombre", "duplicates_rejected.png")

va, vb = val("Replay", "replay_tx")
rd, rr = val("Replay", "sec_detect")[1], val("Replay", "sec_reject")[1]
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.bar(["Retransmis", "Detectes", "Rejetes"], [vb, rd, rr], color=["#6c757d", "#e9c46a", "#2a6f97"])
ax.set_title("Replay avec protection (400 s)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(FIG / "replay_block.png", dpi=150)
plt.close(fig)

va, vb = val("Wormhole", "wormhole_exit")
wd, wr = val("Wormhole", "sec_detect")[1], val("Wormhole", "sec_reject")[1]
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.bar(["EXIT TX", "Detectes", "Rejetes"], [vb, wd, wr], color=["#6c757d", "#e9c46a", "#2a6f97"])
ax.set_title("Wormhole avec protection (400 s)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(FIG / "wormhole_block.png", dpi=150)
plt.close(fig)
print("figures ok", list(FIG.iterdir()))
