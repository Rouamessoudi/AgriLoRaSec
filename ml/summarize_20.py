import csv
from collections import Counter

path = "/home/opp_env/AgriLoRaSec/ml/dataset_20nodes.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8")))
print("n_events", len(rows))
print("columns", list(rows[0].keys()))
print("n_run_id", len({r["run_id"] for r in rows}))
print("Label_logger", dict(Counter(r["Label"] for r in rows)))
print("sender_name", dict(Counter((r.get("sender_name") or "") for r in rows)))

def y_from_name(n):
    n = (n or "").strip()
    if n == "jammer":
        return "Jamming"
    if n == "replayer":
        return "Replay"
    if n == "wormholeB":
        return "Wormhole"
    if n.startswith("loRaNode"):
        return "Normal"
    return None

yc = Counter()
dropped = 0
for r in rows:
    y = y_from_name(r.get("sender_name"))
    if y is None:
        dropped += 1
    else:
        yc[y] += 1
print("Y_from_sender_name", dict(yc))
print("dropped_no_name", dropped)
print("jammer_rows", sum(1 for r in rows if r.get("sender_name") == "jammer"))
print("replayer_rows", sum(1 for r in rows if r.get("sender_name") == "replayer"))
print("wormholeB_rows", sum(1 for r in rows if r.get("sender_name") == "wormholeB"))
print("wormholeA_rows", sum(1 for r in rows if r.get("sender_name") == "wormholeA"))
print("has_sender_name_col", "sender_name" in rows[0])
print("X_must_not_include", ["sender_name", "sender_mac", "run_id", "seed", "Label"])
