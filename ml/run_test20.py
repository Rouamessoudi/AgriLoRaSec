#!/usr/bin/env python3
"""Tests courts 20 nœuds. N'écrit pas dataset.csv."""
import csv
import os
import subprocess
from collections import Counter

SIM = "/home/opp_env/AgriLoRaSec/simulations"
BIN = "/home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec"
NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]
EVENTS = os.path.join(SIM, "results", "packet_events.csv")

SF7 = [
    "--**.loRaNode*.**initialLoRaSF=7",
    "--**.loRaNode*.app[0].initialLoRaSF=7",
    "--**.jammer.**initialLoRaSF=7",
    "--**.jammer.app[0].initialLoRaSF=7",
    "--**.replayer.**initialLoRaSF=7",
    "--**.replayer.app[0].initialLoRaSF=7",
    "--**.wormholeA.**initialLoRaSF=7",
    "--**.wormholeB.**initialLoRaSF=7",
    "--**.wormholeA.app[0].initialLoRaSF=7",
    "--**.wormholeB.app[0].initialLoRaSF=7",
]


def run(config, tlimit, extras):
    if os.path.exists(EVENTS):
        os.remove(EVENTS)
    cmd = [
        BIN, "-u", "Cmdenv", "-c", config,
        f"--sim-time-limit={tlimit}",
        "--cmdenv-express-mode=true",
        f"--output-scalar-file=results/test20_{config}.sca",
        f"--output-vector-file=results/test20_{config}.vec",
        "-n", NED,
    ] + SF7 + extras + LIBS
    print(f"\n===== {config} {tlimit} =====", flush=True)
    proc = subprocess.run(cmd, cwd=SIM, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2500:] if proc.stdout else "")
        print(proc.stderr[-2500:] if proc.stderr else "")
        raise SystemExit(f"FAIL {config} rc={proc.returncode}")
    rows = list(csv.DictReader(open(EVENTS, encoding="utf-8")))
    names = Counter((r.get("sender_name") or "") for r in rows)
    nodes = sorted(n for n in names if n.startswith("loRaNode"))
    print("events", len(rows))
    print("columns", list(rows[0].keys()) if rows else [])
    print("sender_name", dict(names))
    print("n_loRaNode", len(nodes), nodes)
    print("jammer", names.get("jammer", 0), "replayer", names.get("replayer", 0),
          "wormholeB", names.get("wormholeB", 0), "wormholeA", names.get("wormholeA", 0))
    print("Label", dict(Counter((r.get("Label") or "") for r in rows)))
    dest = os.path.join(SIM, "results", f"test20_{config}_events.csv")
    os.replace(EVENTS, dest) if False else open(dest, "w", encoding="utf-8").write(open(EVENTS, encoding="utf-8").read())
    return rows, names, nodes


def main():
    os.makedirs(os.path.join(SIM, "results"), exist_ok=True)
    fast = [
        "--**.loRaNode*.app[0].timeToFirstPacket=1s",
        "--**.loRaNode*.app[0].timeToNextPacket=8s",
    ]
    rows, names, nodes = run("NoAttack20", "30s", fast)
    if len(nodes) < 10:
        raise SystemExit(f"SMOKE FAIL: only {len(nodes)} loRaNode senders")
    run("Jamming20", "20s", fast)
    run("Replay20", "25s", fast)
    run("Wormhole20", "25s", fast)
    print("\nALL_TESTS_DONE")


if __name__ == "__main__":
    main()
