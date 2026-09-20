#!/bin/bash
cd /home/opp_env/AgriLoRaSec/simulations
timeout 40 /home/opp_env/AgriLoRaSec/out/clang-release/src/AgriLoRaSec -u Cmdenv -c Replay \
  --sim-time-limit=5s --cmdenv-express-mode=true --**.vector-recording=false \
  -n .:../src:../../flora-1.2.0/src:../../inet-4.5.4/src \
  -l ../../inet-4.5.4/src/INET -l ../../flora-1.2.0/src/flora \
  > /tmp/replay5.out 2>&1 || true
echo DONE
wc -l /tmp/replay5.out
tail -30 /tmp/replay5.out
