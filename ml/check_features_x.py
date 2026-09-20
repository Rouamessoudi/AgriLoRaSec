import sys
sys.path.insert(0, "/home/opp_env/AgriLoRaSec/ml")
import ml_common as m
print("FEATURES", m.FEATURES)
print("sender_name in X", "sender_name" in m.FEATURES)
print("sender_mac in X", "sender_mac" in m.FEATURES)
assert "sender_name" not in m.FEATURES
assert "sender_mac" not in m.FEATURES
print("OK")
