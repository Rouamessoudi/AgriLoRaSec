# AgriLoRaSec

PFE — Security of an agricultural **LoRa** network using **OMNeT++ / FLoRa**.

## Features
- Agricultural LoRa network (nodes, gateway, network server)
- Attacks: **Jamming**, **Replay**, **Wormhole**
- Simulation configs: `NoAttack`, `Jamming`, `Replay`, `Wormhole`
- Dataset for ML detection (`ml/dataset.csv`)
- Planned models: Random Forest, XGBoost, ANN, LSTM

## Structure
```
AgriLoRaSec/
  src/            # AgriSensorApp, JammerApp, ReplayApp, WormholeApp
  simulations/    # AgriLoRaNetwork, omnetpp.ini
  ml/             # dataset + generation script
```

## Requirements
- OMNeT++ 6.x
- INET 4.5.x
- FLoRa 1.2.x
(Environment used: `opp_env`)

## Author
Roua Messaoudi — Master SSI / Networks
