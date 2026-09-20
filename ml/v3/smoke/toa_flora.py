#!/usr/bin/env python3
import math


def toa(sf, cr=4, bw_hz=125000, payload_bytes=20):
    tsym_ms = (2 ** sf) / (bw_hz / 1000.0)
    tpreamble_s = (8 + 4.25) * tsym_ms / 1000.0
    payload_symb = 8 + math.ceil(
        (8 * payload_bytes - 4 * sf + 28 + 16 - 20 * 0) / (4 * (sf - 2 * 0))
    ) * (cr + 4)
    if payload_symb < 8:
        payload_symb = 8
    body = (8 + payload_symb) * tsym_ms / 1000.0
    dur = tpreamble_s + body
    return tsym_ms, payload_symb, dur, dur + 4.0


print("SF Tsym_ms payloadSymb ToA_s ToA+ClassA_4s ToA/8s cycle/8s")
for sf in range(7, 13):
    tsym, n, dur, cycle = toa(sf)
    print(f"{sf} {tsym:.4f} {n} {dur:.6f} {cycle:.6f} {dur/8:.4f} {cycle/8:.4f}")
print("jammer_SF7_measured_airtime=0.07808")
