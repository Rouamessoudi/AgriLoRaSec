#!/usr/bin/env python3
"""Smoke V3 Replay/Wormhole/Jamming. Ne touche pas aux datasets V1/V2. Pas de campagne."""
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
V2 = ROOT / "ml" / "v2"
V3 = ROOT / "ml" / "v3"
SMOKE = V3 / "smoke"
NED = ".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS = ["-l", "../../inet-4.5.4/src/INET", "-l", "../../flora-1.2.0/src/flora"]

V2_FILES = [
    V2 / "features/dataset_v2_10nodes.csv",
    V2 / "features/dataset_v2_20nodes.csv",
    V2 / "features/dataset_v2_30nodes.csv",
    V2 / "features/dataset_v2_50nodes.csv",
    V2 / "features/dataset_v2_all_nodes.csv",
    V2 / "build_dataset_v2.py",
    ROOT / "ml/dataset.csv",
    ROOT / "ml/dataset_20nodes.csv",
]
FLORA = Path("/home/opp_env/flora-1.2.0/src/LoRa/LoRaMac.cc")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def snapshot():
    out = {str(p): md5(p) for p in V2_FILES + [FLORA] if p.is_file()}
    return out


def run_cfg(cfg: str) -> str:
    SMOKE.mkdir(parents=True, exist_ok=True)
    log = SMOKE / f"{cfg}.log"
    (SIM / "results").mkdir(exist_ok=True)
    cmd = [
        str(BIN), "-u", "Cmdenv", "-c", cfg,
        "--sim-time-limit=120s",
        "--cmdenv-express-mode=true",
        "--**.vector-recording=false",
        f"--output-scalar-file=results/smoke_v3_{cfg}.sca",
        f"--output-vector-file=results/smoke_v3_{cfg}.vec",
        "-n", NED, *LIBS,
    ]
    p = subprocess.run(cmd, cwd=str(SIM), capture_output=True, text=True)
    text = (p.stdout or "") + "\n" + (p.stderr or "")
    log.write_text(text, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(f"FAIL {cfg} rc={p.returncode}")
        print(text[-4000:])
        raise SystemExit(p.returncode)
    return text


def times(lines, pat):
    out = []
    for ln in lines:
        m = re.search(pat, ln)
        if m:
            out.append(ln)
    return out


def parse_t(line):
    m = re.search(r"t=([0-9.]+)", line)
    return float(m.group(1)) if m else None


def check_replay(text):
    lines = text.splitlines()
    cap = [ln for ln in lines if "ReplayApp CAPTURE" in ln]
    rep = [ln for ln in lines if "ReplayApp REPLAY " in ln]
    raw = [ln for ln in lines if "ReplayApp DROP_SELF_RAW" in ln]
    after = [ln for ln in lines if "ReplayApp REPLAY " in ln and (parse_t(ln) or 0) >= 100]
    seqs = set(re.findall(r"ReplayApp CAPTURE .* seq=(-?\d+)", text))
    macs = set(re.findall(r"ReplayApp CAPTURE .* mac=([0-9A-Fa-f:-]+)", text))
    start = any("ReplayApp ATTACK_START" in ln for ln in lines)
    end = any("ReplayApp ATTACK_END" in ln for ln in lines)
    preserved = True
    for ln in rep:
        m = re.search(r"mac=([0-9A-Fa-f:-]+) seq=(-?\d+)", ln)
        if not m:
            preserved = False
            break
        if not any(m.group(1) in c and f"seq={m.group(2)}" in c for c in cap):
            preserved = False
            break
    ok = (
        start and end
        and len(cap) >= 2
        and len(seqs) >= 2
        and len(macs) >= 2
        and len(rep) >= 2
        and len(after) == 0
        and len(raw) >= 1
        and preserved
        and "Error:" not in text
    )
    return {
        "ok": ok,
        "captures": len(cap),
        "unique_seq": sorted(seqs),
        "unique_mac": sorted(macs),
        "replays": len(rep),
        "drop_self_raw": len(raw),
        "replay_after_100s": len(after),
        "attack_start": start,
        "attack_end": end,
        "mac_seq_preserved": preserved,
    }
    # DROP_SELF_RAW is expected (anti-boucle). Fail only if no RAW drop when there were replays is OK either way.


def check_wh(text):
    cap = re.findall(r"WormholeApp CAPTURE .* seq=(-?\d+)", text)
    tun = [ln for ln in text.splitlines() if "WormholeApp TUNNEL A->B" in ln]
    tx = [ln for ln in text.splitlines() if "WormholeApp EXIT TX" in ln]
    raw = [ln for ln in text.splitlines() if "WormholeApp DROP_SELF_RAW" in ln]
    after = [ln for ln in tx if (parse_t(ln) or 0) >= 100]
    ok = (
        "WormholeApp ATTACK_START" in text
        and "WormholeApp ATTACK_END" in text
        and len(cap) >= 2
        and len(set(cap)) >= 2
        and len(tun) >= 2
        and len(tx) >= 2
        and len(after) == 0
        and len(raw) >= 1
        and "Error:" not in text
    )
    return {
        "ok": ok,
        "captures": len(cap),
        "unique_seq": sorted(set(cap)),
        "tunnels": len(tun),
        "exit_tx": len(tx),
        "drop_self_raw": len(raw),
        "tx_after_100s": len(after),
    }


def check_jam(text):
    sends = []
    for ln in text.splitlines():
        if "JammerApp SEND" in ln:
            t = parse_t(ln)
            if t is not None:
                sends.append(t)
    before = [t for t in sends if t < 20 - 1e-9]
    during = [t for t in sends if 20 - 1e-9 <= t < 100]
    after = [t for t in sends if t >= 100]
    ok = (
        "JammerApp ATTACK_START" in text
        and "JammerApp ATTACK_END" in text
        and len(before) == 0
        and len(during) >= 2
        and len(after) == 0
        and "Error:" not in text
    )
    return {
        "ok": ok,
        "n_send": len(sends),
        "before_20": len(before),
        "during": len(during),
        "after_100": len(after),
        "tmin": min(sends) if sends else None,
        "tmax": max(sends) if sends else None,
    }


def main():
    V3.mkdir(exist_ok=True)
    (V3 / "raw").mkdir(exist_ok=True)
    (V3 / "features").mkdir(exist_ok=True)
    (V3 / "reports").mkdir(exist_ok=True)
    SMOKE.mkdir(exist_ok=True)
    before = snapshot()
    (V3 / "reports" / "v2_hashes_before_smoke.json").write_text(json.dumps(before, indent=2), encoding="utf-8")

    r = check_replay(run_cfg("SmokeReplay"))
    w = check_wh(run_cfg("SmokeWormhole"))
    j = check_jam(run_cfg("SmokeJamming"))
    after = snapshot()
    unchanged = before == after
    summary = {
        "replay": r,
        "wormhole": w,
        "jamming": j,
        "v2_hashes_unchanged": unchanged,
        "hashes_before": before,
        "hashes_after": after,
    }
    (SMOKE / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not (r["ok"] and w["ok"] and j["ok"] and unchanged):
        print("V3_ATTACKS_SMOKE_FAILED")
        sys.exit(1)
    print("V3_ATTACKS_SMOKE_VALIDATED")


if __name__ == "__main__":
    main()
