#!/usr/bin/env python3
"""
Génère le dataset 20 nœuds depuis de VRAIES simulations OMNeT++.
Sortie : ml/dataset_20nodes.csv  (ne touche PAS à ml/dataset.csv)
"""
import csv
import os
import subprocess
import sys

SIM_DIR = "/home/opp_env/AgriLoRaSec/simulations"
BIN = "/home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec"
OUT_CSV = "/home/opp_env/AgriLoRaSec/ml/dataset_20nodes.csv"
NED_PATH = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]

CONFIGS = ["NoAttack20", "Jamming20", "Replay20", "Wormhole20"]
SF_LIST = [7, 8, 9, 10, 11, 12]
RUNS_PER_SF = 4
SIM_TIME = "360s"


def sf_overrides(sf):
    """Même SF pour capteurs ET attaquants (pas de SF réservé à une classe)."""
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

FIELDNAMES = [
    "packet_id",
    "recv_time_s",
    "sender_mac",
    "sender_name",
    "receiver_id",
    "rssi_dBm",
    "snir_dB",
    "packet_size_B",
    "transmitted_bytes",
    "energy_consumed",
    "sequence_number",
    "spreading_factor",
    "tx_power_dBm",
    "coding_rate",
    "seq_seen_before",
    "interarrival_s",
    "collision",
    "received",
    "Label",
    "run_id",
    "seed",
]


def run_one(config, seed, run_id, sf):
    result_name = f"PKT20-{config}-SF{sf}-seed{seed}"
    events_src = os.path.join(SIM_DIR, "results", "packet_events.csv")
    if os.path.exists(events_src):
        os.remove(events_src)

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
    ] + sf_overrides(sf) + LIBS

    print(f"[{run_id}] {config} SF={sf} seed={seed} ...", flush=True)
    proc = subprocess.run(cmd, cwd=SIM_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-3000:] if proc.stdout else "", flush=True)
        print(proc.stderr[-3000:] if proc.stderr else "", flush=True)
        raise RuntimeError(f"Simulation failed: {config} SF={sf} seed={seed}")

    if not os.path.exists(events_src):
        raise FileNotFoundError(
            f"{events_src} manquant : PacketEventLogger n'a rien écrit "
            "(compiler AgriLoRaSec et vérifier LoggingPacketForwarder)."
        )

    rows = []
    with open(events_src, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["run_id"] = str(run_id)
            row["seed"] = str(seed)
            rows.append(row)
    print(f"    events={len(rows)} Label={config} SF={sf}", flush=True)
    return rows


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    all_rows = []
    run_id = 1
    for config in CONFIGS:
        for sf in SF_LIST:
            for _ in range(RUNS_PER_SF):
                seed = 4000 + run_id
                all_rows.extend(run_one(config, seed, run_id, sf))
                run_id += 1

    for i, row in enumerate(all_rows, start=1):
        row["packet_id"] = str(i)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDataset 20 noeuds: {OUT_CSV}")
    print(f"Rows: {len(all_rows)}")
    print("ML : X = colonnes radio ; sender_name UNIQUEMENT pour Y, jamais dans X.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
