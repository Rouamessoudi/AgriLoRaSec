#!/usr/bin/env python3
"""Generate AgriLoRaSec ML dataset from OMNeT++ Cmdenv runs (default radio params)."""
import csv
import os
import re
import subprocess
import sys

SIM_DIR = "/home/opp_env/AgriLoRaSec/simulations"
BIN = "/home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec"
OUT_CSV = "/home/opp_env/AgriLoRaSec/ml/dataset.csv"
NED_PATH = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]

CONFIGS = {
    "NoAttack": "normal",
    "Jamming": "jamming",
    "Replay": "replay",
    "Wormhole": "wormhole",
}

RUNS_PER_CONFIG = 5
SIM_TIME = "90s"


def parse_sca(path):
    sent = 0.0
    received = 0.0
    jammer = 0.0
    replay = 0.0
    wormhole = 0.0
    collisions = 0.0

    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("scalar "):
                continue
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            module, name, value = parts[1], parts[2], parts[3]
            try:
                val = float(value)
            except ValueError:
                continue

            if re.search(r"loRaNode\d+\.app\[0\]$", module) and name == "sentPackets":
                sent += val
            elif module.endswith("packetForwarder") and name == "LoRa_GWPacketReceived:count":
                received += val
            elif name == "jammingPacketsSent":
                jammer += val
            elif name == "replayPacketsSent":
                replay += val
            elif name == "wormholePacketsSent":
                wormhole += val
            elif name == "numCollisions":
                collisions += val

    pdr = (received / sent) if sent > 0 else 0.0
    return {
        "packets_sent": int(sent),
        "packets_received": int(received),
        "pdr": round(pdr, 4),
        "jammer_packets": int(jammer),
        "replay_packets": int(replay),
        "wormhole_packets": int(wormhole),
        "collisions": int(collisions),
    }


def run_one(config, seed, run_id):
    result_name = f"ML-{config}-seed{seed}"
    cmd = [
        BIN,
        "-u", "Cmdenv",
        "-c", config,
        f"--sim-time-limit={SIM_TIME}",
        "--cmdenv-express-mode=true",
        f"--seed-set={seed}",
        f"--output-scalar-file=results/{result_name}.sca",
        f"--output-vector-file=results/{result_name}.vec",
        "-n", NED_PATH,
    ] + LIBS

    print(f"[{run_id}] {config} seed={seed} ...", flush=True)
    proc = subprocess.run(cmd, cwd=SIM_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2500:], flush=True)
        print(proc.stderr[-2500:], flush=True)
        raise RuntimeError(f"Simulation failed: {config} seed={seed}")

    sca = os.path.join(SIM_DIR, "results", f"{result_name}.sca")
    if not os.path.exists(sca):
        raise FileNotFoundError(sca)

    metrics = parse_sca(sca)
    metrics["run_id"] = run_id
    metrics["scenario"] = config
    metrics["label"] = CONFIGS[config]
    metrics["seed"] = seed
    return metrics


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    rows = []
    run_id = 1
    for config in CONFIGS:
        for _ in range(RUNS_PER_CONFIG):
            seed = 2000 + run_id
            row = run_one(config, seed, run_id)
            rows.append(row)
            print(
                f"    sent={row['packets_sent']} recv={row['packets_received']} "
                f"pdr={row['pdr']} jam={row['jammer_packets']} rep={row['replay_packets']} "
                f"wh={row['wormhole_packets']} label={row['label']}",
                flush=True,
            )
            run_id += 1

    fieldnames = [
        "run_id",
        "scenario",
        "packets_sent",
        "packets_received",
        "pdr",
        "jammer_packets",
        "replay_packets",
        "wormhole_packets",
        "collisions",
        "label",
        "seed",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDataset written: {OUT_CSV}")
    print(f"Rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
