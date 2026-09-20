#!/bin/bash
set -e
cd /home/opp_env/AgriLoRaSec/simulations
timeout 90 /home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec -u Cmdenv -c SmokeReplay \
  --sim-time-limit=30s --cmdenv-express-mode=true --**.vector-recording=false \
  -n .:../src:../../flora-1.2.0/src:../../inet-4.5.4/src \
  -l ../../inet-4.5.4/src/INET -l ../../flora-1.2.0/src/flora \
  > /tmp/smoke_r.out 2>&1 || true
echo RC_OR_TIMEOUT
wc -l /tmp/smoke_r.out
echo COUNT_ReplayApp
grep -c ReplayApp /tmp/smoke_r.out || true
echo HEAD
grep ReplayApp /tmp/smoke_r.out | head -50
echo TAIL
tail -20 /tmp/smoke_r.out
