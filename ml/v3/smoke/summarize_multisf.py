import re
from pathlib import Path

smoke = Path("/home/opp_env/AgriLoRaSec/ml/v3/smoke")
for sf in range(7, 12):
    for kind in ("SmokeReplay", "SmokeWormhole"):
        p = smoke / f"{kind}_SF{sf}.log"
        print(f"FILE {kind} SF{sf} exists={p.exists()}")
        if not p.exists():
            continue
        t = p.read_text(errors="replace")
        print("  already_transmitting", "already transmitting" in t)
        print("  has_Error", "Error:" in t)
        if kind == "SmokeReplay":
            print("  captures", t.count("ReplayApp CAPTURE"))
            print("  tx", t.count("ReplayApp REPLAY "))
            print("  raw", t.count("ReplayApp DROP_SELF_RAW"))
            for ln in t.splitlines():
                if "ReplayApp ATTACK_END" in ln:
                    print(" ", ln)
            n_after = 0
            for ln in t.splitlines():
                if "ReplayApp REPLAY " in ln:
                    m = re.search(r"t=([0-9.]+)", ln)
                    if m and float(m.group(1)) >= 100:
                        n_after += 1
            print("  tx_after_100", n_after)
        else:
            print("  captures", t.count("WormholeApp CAPTURE"))
            print("  tunnels", t.count("TUNNEL A->B"))
            print("  txB", t.count("EXIT TX"))
            print("  raw", t.count("WormholeApp DROP_SELF_RAW"))
            for ln in t.splitlines():
                if "ATTACK_END role=entry" in ln:
                    print(" ", ln)
            n_after = 0
            for ln in t.splitlines():
                if "EXIT TX" in ln:
                    m = re.search(r"t=([0-9.]+)", ln)
                    if m and float(m.group(1)) >= 100:
                        n_after += 1
            print("  tx_after_100", n_after)
