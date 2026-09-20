#!/usr/bin/env python3
"""Compare Label vs Y on 10-node and 20-node CSVs. Stdlib only."""
import csv
from collections import Counter
from pathlib import Path

ATTACK_MAC = {
    "0A-AA-00-00-00-0C": "Jamming",
    "0A-AA-00-00-00-0D": "Replay",
    "0A-AA-00-00-00-0F": "Wormhole",
}
ATTACK_NAME = {
    "jammer": "Jamming",
    "replayer": "Replay",
    "wormholeB": "Wormhole",
}


def y_mac(mac):
    if not mac or not str(mac).strip():
        return None
    return ATTACK_MAC.get(str(mac).strip().upper(), "Normal")


def y_name(name):
    if not name or not str(name).strip():
        return None
    n = str(name).strip()
    if n in ATTACK_NAME:
        return ATTACK_NAME[n]
    if n.startswith("loRaNode"):
        return "Normal"
    return None


def analyze(path, mode):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    scen = Counter(r["Label"] for r in rows)
    ys = Counter()
    dropped = 0
    for r in rows:
        y = y_name(r.get("sender_name", "")) if mode == "name" else y_mac(r.get("sender_mac", ""))
        if y is None:
            dropped += 1
        else:
            ys[y] += 1
    print("FILE", path)
    print(" rows", len(rows), "runs", len({r["run_id"] for r in rows}))
    print(" scenario Label", dict(scen))
    print(" Y", dict(ys), "dropped", dropped)
    print(" used_for_ML", sum(ys.values()))
    print()


analyze("/home/opp_env/AgriLoRaSec/ml/dataset.csv", "mac")
analyze("/home/opp_env/AgriLoRaSec/ml/dataset_20nodes.csv", "name")
