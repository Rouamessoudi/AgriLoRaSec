# Securite AgriLoRaSec — campagne finale 10 nœuds

## 1. Objectif

Comparer, sur le **même réseau 10 nœuds** que la campagne V3 (1800 s, SF7–12, seeds 0–3) :

attaque **sans** protection vs **avec** protection.

ML V2/V3 inchangé. Distances / puissance / propagation inchangées.

## 2. Configuration 10 nœuds

- Réseau `AgriLoRaNetwork`, `omnetpp.ini` configs `Jamming` / `Replay` / `Wormhole` / `NoAttack`
- Protections : `JammingProtected` (hop 868.0→868.3 MHz à t=360 s), `ReplayProtected` et `WormholeProtected` (filtre GW MAC+seq)
- Contrôle : `NoAttackProtected` (hop + filtre)

## 3. Protocole

- BEFORE : runs V3 `ml/v3/raw/10nodes/` réutilisés (1800 s, mêmes SF/seeds/configs d'attaque)
- AFTER : nouveaux runs uniquement `*Protected`
- Réutilisés : 96 ; manquants BEFORE : 0
- Nouveaux runs demandés : 96
- Réussis : 96 ; skip déjà faits : 0 ; échoués : 0

## 4. Jamming

Protection = channel hop des nœuds légitimes, jammer reste à 868 MHz.

- Collisions BEFORE : 131.2 ± 25.26
- Collisions AFTER : 4.875 ± 3.392
- PDR BEFORE : 0.3071 ± 0.182
- PDR AFTER : 0.4503 ± 0.3062

## 5. Replay

Replay RAW + filtre first-seen. Une RAW TX n'est pas une RAW RX.

- RAW TX AFTER : 111.7 ± 38.97
- RAW RX GW AFTER : 41.71 ± 26.05
- True duplicate pairs AFTER : 23.96 ± 19.61
- Detected AFTER : 23.96 ± 19.61
- Rejected AFTER : 23.96 ± 19.61
- Taux de rejet si opportunité : 100.0% (rejet/detection moyenne)

## 6. Wormhole

Même filtre, topologie étoile.

- EXIT TX AFTER : 121.4 ± 48.99
- EXIT RX GW AFTER : 43.62 ± 25.78
- True duplicate pairs AFTER : 22.17 ± 16.9
- Rejected AFTER : 22.17 ± 16.9
- Taux de rejet si opportunité : 100.0% (rejet/detection moyenne)

## 7. Comparaison BEFORE/AFTER

Voir `tables/security_10nodes_detailed.csv` et `tables/security_10nodes_summary.csv`.

## 8. Faux positifs (Normal)

False rejects AFTER : 0 ± 0

## 9. Limites

Le filtre Replay/Wormhole n'agit que si **original et copie** sont tous deux décodés à la GW.
Les pertes de portée V3 restent. Aucun paramètre radio n'a été modifié pour forcer des rejets.

## 10. Conclusion

**IMPLEMENTATION CORRECTE**

- Jamming hop : oui (FLoRa collision = même CF)
- Replay/Wormhole filtre MAC+seq à `LoggingPacketForwarder` : oui

**EFFICACITÉ EXPÉRIMENTALEMENT OBSERVÉE**

- JAMMING PROTECTION EXPERIMENTALLY VALIDATED: YES
- REPLAY PROTECTION EXPERIMENTALLY VALIDATED: YES
- WORMHOLE PROTECTION EXPERIMENTALLY VALIDATED: YES
