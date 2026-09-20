#!/bin/bash
set -euo pipefail
BIN=/home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec
SIM=/home/opp_env/AgriLoRaSec/simulations
NED=".:../src:../../flora-1.2.0/src:../../inet-4.5.4/src"
LIBS="-l ../../inet-4.5.4/src/INET -l ../../flora-1.2.0/src/flora"
cd "$SIM"
mkdir -p results

echo "===== INIT COUNT NoAttack20 1s ====="
rm -f results/init20.log results/packet_events.csv
$BIN -u Cmdenv -c NoAttack20 --sim-time-limit=1s --cmdenv-express-mode=false \
  --cmdenv-log-level=info \
  --output-scalar-file=results/test20_init.sca \
  --output-vector-file=results/test20_init.vec \
  -n "$NED" $LIBS > results/init20.log 2>&1
echo -n "AgriSensorApp init lines: "
grep -c "AgriSensorApp init" results/init20.log || true
echo "loRaNode names in init log:"
grep "AgriSensorApp init on loRaNode" results/init20.log | sed 's/.*on //' | sort

run_cfg() {
  local cfg="$1"
  local tlimit="$2"
  rm -f results/packet_events.csv
  echo "===== RUN $cfg t=$tlimit ====="
  $BIN -u Cmdenv -c "$cfg" --sim-time-limit="$tlimit" --cmdenv-express-mode=true \
    --**.loRaNode*.**initialLoRaSF=7 \
    --**.loRaNode*.app[0].initialLoRaSF=7 \
    --**.jammer.**initialLoRaSF=7 \
    --**.jammer.app[0].initialLoRaSF=7 \
    --**.replayer.**initialLoRaSF=7 \
    --**.replayer.app[0].initialLoRaSF=7 \
    --**.wormholeA.**initialLoRaSF=7 \
    --**.wormholeB.**initialLoRaSF=7 \
    --**.wormholeA.app[0].initialLoRaSF=7 \
    --**.wormholeB.app[0].initialLoRaSF=7 \
    --output-scalar-file=results/test20_${cfg}.sca \
    --output-vector-file=results/test20_${cfg}.vec \
    -n "$NED" $LIBS
  python3 - "$cfg" << 'PY'
import csv, sys
from collections import Counter
cfg = sys.argv[1]
path = "results/packet_events.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8")))
print("events", len(rows))
if not rows:
    raise SystemExit("NO EVENTS for " + cfg)
print("columns", list(rows[0].keys()))
names = Counter((r.get("sender_name") or "") for r in rows)
print("sender_name", dict(names))
nodes = sorted(n for n in names if n.startswith("loRaNode"))
print("n_loRaNode_senders", len(nodes), nodes)
print("jammer", names.get("jammer", 0), "replayer", names.get("replayer", 0),
      "wormholeB", names.get("wormholeB", 0), "wormholeA", names.get("wormholeA", 0))
print("Label", dict(Counter((r.get("Label") or "") for r in rows)))
open("results/test20_%s_events.csv" % cfg, "w", encoding="utf-8").write(open(path, encoding="utf-8").read())
PY
}

run_cfg NoAttack20 90s
run_cfg Jamming20 20s
run_cfg Replay20 30s
run_cfg Wormhole20 30s
echo ALL_TESTS_DONE
