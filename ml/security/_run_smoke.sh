#!/bin/bash
set -euo pipefail
cd /home/opp_env/AgriLoRaSec
PY=/home/opp_env/AgriLoRaSec/ml/v2/ml/.venv/bin/python
if [ -x "$PY" ]; then
  "$PY" ml/security/run_security.py smoke
else
  python3 ml/security/run_security.py smoke
fi
