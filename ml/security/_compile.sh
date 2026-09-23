#!/bin/bash
set -euo pipefail
cd /home/opp_env/AgriLoRaSec
make -j$(nproc)
