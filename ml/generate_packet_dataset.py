#!/usr/bin/env python3
"""
Génère le dataset final (événements GW) depuis de VRAIES simulations OMNeT++.
Sortie unique : ml/dataset.csv
Label = config du run (état du réseau), pas un label par émetteur.
"""
import csv
import os
import subprocess
import sys

SIM_DIR = "/home/opp_env/AgriLoRaSec/simulations"
BIN = "/home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec"
OUT_CSV = "/home/opp_env/AgriLoRaSec/ml/dataset.csv"
NED_PATH = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]

# Une attaque à la fois. Le SF varie de 7 à 12 DANS CHAQUE scénario
# (même liste partout) pour que energy_consumed change via l'airtime FLoRa
# sans que SF ⇒ Label. FLoRa fixe payloadBytes=20 dans LoRaTransmitter :
# changer le SF suffit (ToA ∝ 2^SF). On ne touche pas à FLoRa.
CONFIGS = ["NoAttack", "Jamming", "Replay", "Wormhole"]
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

# Colonnes écrites par PacketEventLogger (ordre figé)
FIELDNAMES = [
    "packet_id",
    "recv_time_s",
    "sender_mac",
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
    "run_id",   # métadonnée de concaténation, PAS une feature d'attaque
    "seed",     # métadonnée, à retirer avant l'entraînement
]


def run_one(config, seed, run_id, sf):
    result_name = f"PKT-{config}-SF{sf}-seed{seed}"
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

    # Identifiant de ligne unique après concaténation (pas une mesure radio)
    for i, row in enumerate(all_rows, start=1):
        row["packet_id"] = str(i)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDataset officiel: {OUT_CSV}")
    print(f"Rows: {len(all_rows)}")
    print("ML : X = colonnes radio ; y = Label. Retirer run_id et seed avant fit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
