#!/bin/bash
set -euo pipefail
export V2_WORKERS="${V2_WORKERS:-4}"
export V2_SIM_TIME=1800s
unset V2_MAX_JOBS || true
python3 /home/opp_env/AgriLoRaSec/ml/v2/run_campaign_v2.py
echo CAMPAIGN_EXIT:$?
