#!/usr/bin/env python3
"""Rejoue le run 8s NoAttack_sf7_s0 en 1800s puis rebuild 10nodes + concat."""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/home/opp_env/AgriLoRaSec/ml/v2")
import run_campaign_v2 as c

os.environ["V2_SIM_TIME"] = "1800s"
c.SIM_TIME = "1800s"
job = c.job_paths(10, "Normal", 7, 0)
for p in (job["okflag"], job["csv"], job["log"]):
    if p.exists():
        p.unlink()
print("rerun", job["stem"], flush=True)
r = c.run_job(job)
print(r, flush=True)
if r.get("status") != "ok":
    sys.exit(1)
c.build_features()  # rebuilds all 4 - a bit extra but consistent
dest, n = c.concat_all()
print("concat", dest, n)
c.write_integrity("after_repair")
