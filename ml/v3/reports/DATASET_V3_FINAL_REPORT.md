# Dataset V3 final — campagne scalabilite

Statut: DATASET_V3_FINAL_READY

Protocole: 4 tailles x 4 scenarios x 6 SF x 4 seeds = 384 runs uniques, 1800 s, attackStart=360, attackEnd=1440, W=60 s. Pas de ML.

## Runs

- 383/384 OK a la premiere passe.
- Echec unique: Wormhole_sf10_s3 (10 nodes, Wormhole, SF10, seed 3) a t=1120.65s — AgriSensorApp peekAtFront LoRaAppPacket alors que le front etait LoRaMacFrame (ADR/downlink Class A). Relance unique apres garde RX (AgriSensorApp seulement). Succes, 1800 s.
- Relance: 1 fichier ecrase (copie unique), aucune duplication artificielle.
- Final: 384/384 complete_1800s, 96 CSV uniques par taille.

## RAW (lignes evenements)

| N | runs | raw_rows | RX GW | collisions GW | GW utilisables | omniscients exclus | ratio vs 10 |
|---|------|----------|-------|---------------|----------------|--------------------|-------------|
| 10 | 96 | 111386 | 23988 | 3844 | 27832 | 83554 | 1.00 |
| 20 | 96 | 137862 | 32933 | 8715 | 41648 | 96214 | 1.24 |
| 30 | 96 | 163053 | 38588 | 14267 | 52855 | 110198 | 1.46 |
| 50 | 96 | 215742 | 49051 | 27142 | 76193 | 139549 | 1.94 |

Le volume RAW et les collisions GW augmentent avec N. Les datasets fenetres restent a 2880 lignes/taille (fenetre fixe).

## Features

- dataset_v3_10nodes.csv : 2880 fenetres, 96 run_id
- dataset_v3_20nodes.csv : 2880
- dataset_v3_30nodes.csv : 2880
- dataset_v3_50nodes.csv : 2880
- dataset_v3_all_nodes.csv : 11520 fenetres, 384 run_id

30 fenetres/run. 24 runs par scenario et par taille. 6 SF, 4 seeds. 0 fenetre mixte (limites alignees W=60).

Labels par taille: Normal 1584, Jamming 432, Replay 432, Wormhole 432.
Global: Normal 6336, Jamming 1728, Replay 1728, Wormhole 1728.

14 features V2 conservees. Label = fenetre programmee, pas duplicate_rate.

## Jamming (fenetres Label=Jamming)

| N | packet_rate moyen | collision_intensity moyenne |
|---|-------------------|------------------------------|
| 10 | 0.626 | 0.119 |
| 20 | 0.636 | 0.238 |
| 30 | 0.633 | 0.352 |
| 50 | 0.641 | 0.575 |

packet_rate stable; collision_intensity augmente avec N.

## Replay (18 fenetres actives x 24 runs = 432)

| N | fenetres actives | dup_rate>0 | % | runs avec au moins 1 dup GW |
|---|------------------|------------|---|------------------------------|
| 10 | 432 | 251 | 58.1 | 21/24 |
| 20 | 432 | 290 | 67.1 | 22/24 |
| 30 | 432 | 298 | 69.0 | 22/24 |
| 50 | 432 | 295 | 68.3 | 21/24 |

## Wormhole

| N | fenetres actives | dup_rate>0 | % | runs avec au moins 1 dup GW |
|---|------------------|------------|---|------------------------------|
| 10 | 432 | 247 | 57.2 | 20/24 |
| 20 | 432 | 307 | 71.1 | 24/24 |
| 30 | 432 | 299 | 69.2 | 21/24 |
| 50 | 432 | 301 | 69.7 | 22/24 |

Observation: plus de one-shot V2 (une seule fenetre). Une fraction de runs n a aucune duplication GW (PHY/collisions), non corrige volontairement.

## Integrite V1/V2 / FLoRa / attaques

MD5 inchanges (before==after): datasets V1/V2, build_dataset_v2.py, ReplayApp, WormholeApp, JammerApp, PreserveHeaderLoRaMac, flora LoRaMac.cc.

Aucun train/test. Aucun RF/XGB/ANN/LSTM.

AgriSensorApp: garde RX (dynamicPtrCast / pop LoRaMacFrame) uniquement pour terminer Wormhole_sf10_s3. Politique attaques inchangee.
