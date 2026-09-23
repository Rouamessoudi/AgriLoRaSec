# Rapport securite AgriLoRaSec

## 1. Objectif

Ajouter une couche **defense / mitigation** distincte du ML :

- le ML (V2/V3) classe des **fenetres de 60 s** (Normal / Jamming / Replay / Wormhole) ;
- la securite agit **paquet par paquet** dans OMNeT++ / FLoRa.

Les campagnes V2/V3 n’ont pas ete relancees ni ecrasees.

## 2. Audit (versions FINALES utilisees)

| Attaque | Implementation reelle |
|---|---|
| Jamming | `JammerApp` + `JammerNode` / `JammerSafeLoRaMac` / `JammerSafeLoRaRadio` |
| Replay RAW | `ReplayApp` capture `signalAdded` sur `LoRaMedium`, rejoue le `LoRaMacFrame` via `ReplayLoRaNic` + `PreserveHeaderLoRaMac` (`REPLAY_RAW_KIND`) |
| Wormhole | `WormholeApp` role `entry` (A = `LoRaNode`) tunnel vers `exit` (`WormholeExitNode` / meme NIC RAW), `tunnelDelay` variable |
| Gateway | `AgriLoRaGW` + `LoggingPacketForwarder` + `PacketEventLogger` |
| Topologie | etoile 10/20/30/50, **pas de routage multi-hop** |

`seq_seen_before` existait deja dans le logger (statistique). **Il ne rejetait pas** le paquet.

## 3. Protection Jamming

FLoRa ne compte une collision que si `loRaReception->getLoRaCF() == loRaInterference->getLoRaCF()` (`LoRaReceiver.cc`).

Mitigation reelle : **hop 868.0 MHz → 868.3 MHz** (canal EU868) sur les **noeuds legitimes uniquement**, a `channelHopTime`. Le jammer reste a 868.0 MHz. Les `LoRaTag` des paquets suivants utilisent `getCF()` = nouvelle frequence.

La gateway FLoRa (`iAmGateway`) recoit tous les CF ; le hop n’est donc pas un faux affichage : l’interference change bien.

Parametres (defaut **off** pour ne pas casser V2/V3) :

- `**.loRaNode*.app[0].enableChannelHop`
- configs `JammingProtected` / `SmokeJammingProtected`

## 4. Protection Replay

Filtre gateway **first-seen (transmitterAddress, sequenceNumber)** dans `LoggingPacketForwarder` :

- 1er (MAC, seq) → acceptation + memorisation (cache session, duree = simulation) ;
- suivant → detection + **rejet** (non envoye au Network Server).

Ce n’est pas du ML. Compatible Replay RAW car le header MAC/seq est preserve.

## 5. Protection Wormhole

Pas de reroutage (reseau en etoile).

Meme filtre de doublons : le wormhole retransmet le **meme** `LoRaMacFrame`. Si l’original a deja ete accepte, la copie EXIT est rejetee.

**Limite assumee :** si l’original n’atteint jamais la GW, la copie wormhole est le 1er (MAC, seq) et **est acceptee**. On ne pretend pas identifier l’attaquant au paquet pres via le classifieur 60 s.

ML et mitigation restent **deux experiences complementaires**.

## 6. Protocole experimental

- Smoke 120 s, SF7, 10 noeuds, seed 0.
- Evaluation 400 s, memes configs smoke, `attackEnd=380s`.
- Resultats dans `ml/security/` uniquement.
- Temoin `SmokeNoAttackProtected` : hop + filtre, mesure des faux rejets.

## 7. Resultats avant / apres (evaluation 400 s, valeurs reelles)

Source : `ml/security/features/comparison_eval.csv`.

### Jamming

| Metric | Sans | Avec | Diff |
|---|---:|---:|---:|
| Collisions GW | 178 | 5 | **-173** |
| PDR unique | 0.041 | 0.041 | 0 |
| RX uniques | 12 | 12 | 0 |
| Noeuds hop | 0 | 10 | +10 |

Le hop **reduit fortement les collisions loggees**. Le PDR unique ne change pas ici : les pertes restantes sont surtout de **portee / non-reception**, pas ces collisions.

### Replay

| Metric | Sans | Avec | Diff |
|---|---:|---:|---:|
| Replay retransmis | 87 | 87 | 0 |
| Doublons detectes / rejetes a la GW | 0 | 0 | 0 |
| `seq_seen_before` PHY | 0 | 0 | 0 |
| Faux rejets (trafic Normal protege) | — | **0** | |

87 retransmissions RAW ont bien lieu. **Aucune n’apparait comme 2e reception PHY** du meme (MAC, seq) a la gateway dans ces runs. Le filtre n’a donc **rien a rejeter**. On ne conclut pas a une efficacite de blocage.

### Wormhole

| Metric | Sans | Avec | Diff |
|---|---:|---:|---:|
| EXIT TX | 87 | 87 | 0 |
| Doublons detectes / rejetes | 0 | 0 | 0 |

Meme constat : copies RAW emises, pas de 2e RX (MAC, seq) a la GW.

### Temoin Normal + protections

`SmokeNoAttackProtected` 400 s : **0 rejet**, 10 hops, PDR ~0.03 (faible a cause de la geometrie, pas du filtre).

## 8. Interpretation

- Defense jamming **physiquement coherente** avec FLoRa ; effet mesure sur les **collisions**.
- Defense Replay/Wormhole **logiquement correcte** (anti-doublon MAC+seq). Dans la topologie et ces durees, le canal ne livre pas les deux copies a la GW, donc **taux de blocage observe = 0/0** (indetermine, pas un succes).
- Ne pas fusionner avec le ML V3 : une fenetre « Replay » n’identifie pas le paquet a supprimer.

## 9. Limites

1. PDR global bas (10 noeuds, positions NED, 400 s) : beaucoup de TX hors portee.
2. RAW Replay/Wormhole : TX observes dans les logs, souvent **non recus** a la GW → filtre inactif.
3. Cache anti-replay : session entiere, pas de wrap de seq dans nos durees.
4. Hop : le jammer ne suit pas (attaquant non adaptatif), hypothese explicite.
5. Pas d’integration ML → drop automatique.

## 10. Conclusion

Les trois protections sont **implementees**, les smoke tests **terminent**, V2/V3 **intacts**.

- Jamming : mitigation radio **demontree** (collisions 178 → 5).
- Replay / Wormhole : mecanisme **defendable**, **pas d’efficacite de blocage demontree** sur ces traces (0 doublon PHY a la GW).

Sauvegarde des sources avant patch : `backup_before_security/`.
