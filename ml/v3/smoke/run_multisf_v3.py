#!/usr/bin/env python3
"""Validation Replay/Wormhole SF7-SF12. Pas de campagne, pas de dataset V3."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/opp_env/AgriLoRaSec")
SIM = ROOT / "simulations"
BIN = ROOT / "out/clang-release/src/AgriLoRaSec"
SMOKE = ROOT / "ml/v3/smoke"
NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]
V_FILES = [
    ROOT / "ml/v2/features/dataset_v2_10nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_20nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_30nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_50nodes.csv",
    ROOT / "ml/v2/features/dataset_v2_all_nodes.csv",
    ROOT / "ml/v2/build_dataset_v2.py",
    ROOT / "ml/dataset.csv",
    ROOT / "ml/dataset_20nodes.csv",
    Path("/home/opp_env/flora-1.2.0/src/LoRa/LoRaMac.cc"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def snapshot():
    return {str(p): md5(p) for p in V_FILES if p.is_file()}


def parse_t(line):
    m = re.search(r"t=([0-9.]+)", line)
    return float(m.group(1)) if m else None


def intervals(times):
    if len(times) < 2:
        return {"n": len(times), "mean": None, "min": None, "max": None, "all_8s": False, "dts": []}
    dts = [times[i] - times[i - 1] for i in range(1, len(times))]
    all_8 = all(abs(d - 8.0) < 0.02 for d in dts)
    return {
        "n": len(times),
        "mean": sum(dts) / len(dts),
        "min": min(dts),
        "max": max(dts),
        "all_8s": all_8,
        "dts": [round(d, 4) for d in dts[:8]],
    }


def run(cfg: str, sf: int):
    log = SMOKE / f"{cfg}_SF{sf}.log"
    extra = [
        f"--**.loRaNode*.app[0].initialLoRaSF={sf}",
        # Campagne: exponential(50s). Smoke exponential(6s) + SF12 airTime gate 171s = hang CPU.
        "--**.loRaNode*.app[0].timeToNextPacket=exponential(50s)",
        "--**.loRaNode*.app[0].timeToFirstPacket=exponential(50s)",
    ]
    if cfg == "SmokeReplay":
        extra.append(f"--**.replayer.app[0].initialLoRaSF={sf}")
    else:
        extra.append(f"--**.wormholeA.app[0].initialLoRaSF={sf}")
        extra.append(f"--**.wormholeB.app[0].initialLoRaSF={sf}")
    cmd = [
        str(BIN), "-u", "Cmdenv", "-c", cfg,
        "--sim-time-limit=180s",
        "--cmdenv-express-mode=true",
        "--**.vector-recording=false",
        f"--output-scalar-file=results/multisf_sf{sf}_{cfg}.sca",
        f"--output-vector-file=results/multisf_sf{sf}_{cfg}.vec",
        "-n", NED, *LIBS, *extra,
    ]
    # Fenetre smoke 20-100s conservee (configs Smoke*). sim 180s pour voir attackEnd.
    p = subprocess.run(cmd, cwd=str(SIM), capture_output=True, text=True)
    text = (p.stdout or "") + "\n" + (p.stderr or "")
    log.write_text(text, encoding="utf-8", errors="replace")
    return text, p.returncode


def airtime_logs(text, prefix):
    vals = [float(x) for x in re.findall(rf"{prefix} PHY_TX_END .* airtime=([0-9.]+)s", text)]
    return vals


def summarize_replay(text, rc):
    cap = [ln for ln in text.splitlines() if "ReplayApp CAPTURE" in ln]
    tx = [ln for ln in text.splitlines() if "ReplayApp REPLAY " in ln]
    raw = [ln for ln in text.splitlines() if "ReplayApp DROP_SELF_RAW" in ln]
    end = [ln for ln in text.splitlines() if "ReplayApp ATTACK_END" in ln]
    dropq = None
    if end:
        m = re.search(r"dropQ=(\d+)", end[0])
        dropq = int(m.group(1)) if m else None
    times = [parse_t(ln) for ln in tx]
    times = [t for t in times if t is not None]
    after = [t for t in times if t >= 100]
    seqs = set(re.findall(r"ReplayApp CAPTURE .* seq=(-?\d+)", text))
    macs = set(re.findall(r"ReplayApp CAPTURE .* mac=([0-9A-Fa-f:-]+)", text))
    radio_err = "already transmitting" in text
    fatal = "Error:" in text and "Simulation time limit reached" not in text
    iv = intervals(times)
    ok = (
        rc == 0 and not radio_err and not fatal
        and len(cap) >= 2 and len(tx) >= 2 and len(after) == 0
        and len(seqs) >= 1 and len(macs) >= 2 and len(raw) >= 1
        and not iv["all_8s"]
    )
    return {
        "ok": ok, "rc": rc, "captures": len(cap), "tx_raw": len(tx),
        "drop_queue": dropq, "drop_self_raw": len(raw),
        "unique_seq": sorted(seqs), "unique_mac_n": len(macs),
        "tx_first": times[0] if times else None, "tx_last": times[-1] if times else None,
        "tx_after_100": len(after), "radio_error": radio_err, "fatal_error": fatal,
        "interval": iv, "phy_airtime": airtime_logs(text, "ReplayApp"),
    }


def summarize_wh(text, rc):
    cap = re.findall(r"WormholeApp CAPTURE .* seq=(-?\d+)", text)
    tun = [ln for ln in text.splitlines() if "WormholeApp TUNNEL A->B" in ln]
    tx = [ln for ln in text.splitlines() if "WormholeApp EXIT TX" in ln]
    raw = [ln for ln in text.splitlines() if "WormholeApp DROP_SELF_RAW" in ln]
    end = [ln for ln in text.splitlines() if "WormholeApp ATTACK_END role=entry" in ln]
    dropq = None
    if end:
        m = re.search(r"dropQ=(\d+)", end[0])
        dropq = int(m.group(1)) if m else None
    times = [parse_t(ln) for ln in tx]
    times = [t for t in times if t is not None]
    after = [t for t in times if t >= 100]
    macs = set(re.findall(r"WormholeApp CAPTURE .* mac=([0-9A-Fa-f:-]+)", text))
    radio_err = "already transmitting" in text
    fatal = "Error:" in text and "Simulation time limit reached" not in text
    iv = intervals(times)
    ok = (
        rc == 0 and not radio_err and not fatal
        and len(cap) >= 2 and len(macs) >= 2 and len(tun) >= 2
        and len(tx) >= 2 and len(after) == 0 and len(raw) >= 1
        and not iv["all_8s"]
    )
    return {
        "ok": ok, "rc": rc, "captures_A": len(cap), "tunnels": len(tun),
        "tx_B": len(tx), "drop_queue": dropq, "drop_self_raw": len(raw),
        "unique_seq": sorted(set(cap)), "unique_mac_n": len(macs),
        "tx_first": times[0] if times else None, "tx_last": times[-1] if times else None,
        "tx_after_100": len(after), "radio_error": radio_err, "fatal_error": fatal,
        "interval": iv, "phy_airtime": airtime_logs(text, "WormholeApp"),
    }


def main():
    SMOKE.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    out = {"replay": {}, "wormhole": {}}
    all_ok = True
    for sf in range(7, 13):
        print(f"RUN Replay SF{sf}", flush=True)
        t, rc = run("SmokeReplay", sf)
        out["replay"][f"SF{sf}"] = summarize_replay(t, rc)
        print(f"Replay SF{sf}", json.dumps(out["replay"][f"SF{sf}"]), flush=True)
        if not out["replay"][f"SF{sf}"]["ok"]:
            all_ok = False
        print(f"RUN Wormhole SF{sf}", flush=True)
        t, rc = run("SmokeWormhole", sf)
        out["wormhole"][f"SF{sf}"] = summarize_wh(t, rc)
        print(f"Wormhole SF{sf}", json.dumps(out["wormhole"][f"SF{sf}"]), flush=True)
        if not out["wormhole"][f"SF{sf}"]["ok"]:
            all_ok = False
    after = snapshot()
    out["v2_hashes_unchanged"] = before == after
    out["hashes_before"] = before
    out["hashes_after"] = after
    out["all_ok"] = all_ok and before == after
    (SMOKE / "multisf_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("replay", "wormhole", "v2_hashes_unchanged", "all_ok")}, indent=2), flush=True)
    sys.exit(0 if out["all_ok"] else 1)


if __name__ == "__main__":
    main()
