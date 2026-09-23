# Campagne 10 nœuds — audit de comparabilité

BEFORE (réutilisé, non relancé) : `ml/v3/raw/10nodes/{Jamming,Replay,Wormhole,NoAttack}_sf{7-12}_s{0-3}`
- 1800 s, seed-set, SF override identique à V3
- 24 ok par scénario (96 runs)

AFTER (nouveaux) : configs `*Protected` déjà dans omnetpp.ini
- JammingProtected = Jamming + hop t=360s 868.3 MHz
- ReplayProtected = Replay + enableDuplicateFilter
- WormholeProtected = Wormhole + enableDuplicateFilter
- NoAttackProtected = NoAttack + hop + filtre

Aucune modification de distance, TX power, positions, attaques, V2/V3.
