#!/usr/bin/env python3
import csv, hashlib, json, math, statistics
from collections import defaultdict
from pathlib import Path

FEAT = Path("/home/opp_env/AgriLoRaSec/ml/v2/features")
X = [
    "packet_rate","gw_success_rate","collision_rate","collision_intensity","duplicate_rate",
    "mean_duplicate_delay_s","min_duplicate_delay_s","max_duplicate_delay_s",
    "mean_rssi","std_rssi","mean_snir","std_snir","interarrival_mean","interarrival_std",
]
FORB = {"sender_name","sender_mac","sequence_number","packet_id","packet_size_B",
        "transmitted_bytes","energy_consumed","tx_power_dBm","coding_rate","seq_seen_before"}

def fnum(x):
    try:
        if x is None or str(x).strip()=="": return math.nan
        return float(x)
    except Exception:
        return math.nan

def summarize(path):
    rows=list(csv.DictReader(path.open()))
    header=list(rows[0].keys()) if rows else []
    leak=[c for c in X if c in FORB]
    extra=[c for c in X if c not in header]
    runs=sorted(set(r["run_id"] for r in rows))
    labels=defaultdict(int)
    sfs=defaultdict(int)
    seeds=defaultdict(int)
    nn=defaultdict(int)
    for r in rows:
        labels[r["Label"]]+=1
        sfs[r["SF"]]+=1
        seeds[r["seed"]]+=1
        nn[r["n_nodes"]]+=1
    wset=sorted(set(float(r["window_end_s"])-float(r["window_start_s"]) for r in rows))
    nans={k:0 for k in X}
    dups=defaultdict(int)
    stats={}
    by=defaultdict(list)
    for r in rows:
        by[r["Label"]].append(r)
        for k in X:
            v=fnum(r[k])
            if math.isnan(v): nans[k]+=1
        if fnum(r["duplicate_rate"])>0:
            dups[r["Label"]]+=1
    for lab, rs in by.items():
        stats[lab]={}
        for k in X:
            xs=[fnum(r[k]) for r in rs]
            fin=[x for x in xs if not math.isnan(x)]
            stats[lab][k]={
                "mean": statistics.fmean(fin) if fin else math.nan,
                "median": statistics.median(fin) if fin else math.nan,
                "std": statistics.stdev(fin) if len(fin)>1 else math.nan,
                "nan": sum(1 for x in xs if math.isnan(x)),
            }
    jam_pr=statistics.fmean([fnum(r["packet_rate"]) for r in by.get("Jamming",[])])
    jam_ci=statistics.fmean([fnum(r["collision_intensity"]) for r in by.get("Jamming",[])])
    return {
        "file": path.name, "nrows": len(rows), "n_runs": len(runs),
        "labels": dict(labels), "sfs": dict(sfs), "seeds": dict(seeds), "n_nodes": dict(nn),
        "W": wset, "leak_x": leak, "missing_x": extra, "header_ok": all(c in header for c in X),
        "dups": dict(dups), "nans": nans, "jam_pr": jam_pr, "jam_ci": jam_ci, "stats": stats,
        "forbidden_in_header_as_x": [c for c in header if c in FORB and c in X],
    }

def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()

out=[]
for n in (10,20,30,50):
    s=summarize(FEAT/f"dataset_v2_{n}nodes.csv")
    out.append(s)
    print(f"== {n} nodes rows={s['nrows']} runs={s['n_runs']} W={s['W']} labels={s['labels']}")
    print(f"   SF={s['sfs']} seeds={s['seeds']} dups={s['dups']}")
    print(f"   jam_pr={s['jam_pr']:.4f} jam_ci={s['jam_ci']:.4f} headerX={s['header_ok']} leak={s['leak_x']}")
sall=summarize(FEAT/"dataset_v2_all_nodes.csv")
print("ALL", sall["nrows"], sall["n_runs"], sall["n_nodes"], sall["labels"])
print("validation exists", (FEAT/"dataset_v2_validation_10nodes.csv").exists())
files=[
 "/home/opp_env/AgriLoRaSec/src/ReplayApp.cc",
 "/home/opp_env/AgriLoRaSec/src/WormholeApp.cc",
 "/home/opp_env/AgriLoRaSec/src/JammerApp.cc",
 "/home/opp_env/AgriLoRaSec/src/PreserveHeaderLoRaMac.cc",
 "/home/opp_env/AgriLoRaSec/src/PacketEventLogger.cc",
 "/home/opp_env/flora-1.2.0/src/LoRa/LoRaMac.cc",
 "/home/opp_env/AgriLoRaSec/ml/dataset.csv",
 "/home/opp_env/AgriLoRaSec/ml/dataset_20nodes.csv",
]
for f in files:
    print(md5(f), f)
Path("/home/opp_env/AgriLoRaSec/ml/v2/reports/final_campaign_summary.json").write_text(
    json.dumps({"per":out,"all":{k:sall[k] for k in sall if k!="stats"}}, indent=2, default=str))
