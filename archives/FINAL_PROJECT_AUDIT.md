# AgriLoRaSec — AUDIT FINAL COMPLET

Date : 2026-09-23  
Projet audité : `/home/opp_env/AgriLoRaSec` (WSL distro `opp_env`)  
Méthode : lecture du code, NED/INI, CSV, logs, modèles. **Aucun dataset, attaque, résultat ou modèle n’a été modifié.** Seul ce fichier d’audit a été ajouté. Un script temporaire d’agrégation a été exécuté puis **supprimé**.

Compilation incrémentale vérifiée. Campagnes 384 runs / sécurité 1800 s **non relancées**.

---

## Verdict strict

**TECHNICALLY READY FOR DEFENSE: YES**

Le cœur scientifique (réseau LoRa 10–50 nœuds, trois attaques, logger, datasets V2/V3 2880×4, ML V3, campagne sécurité 10 nœuds BEFORE/AFTER) est **présent, cohérent et recalculable** à partir des fichiers. Les chiffres de sécurité cités dans le rapport (`collisions 131.17→4.875`, `PDR 0.307→0.450`, `23.96` / `22.17` rejects, faux positifs `0`) **ne sont pas inventés** : ils se recalculent depuis `security_10nodes_detailed.csv`.

Ce YES n’est **pas** une validation automatique. Il suppose que la soutenance présente **V3 + `ml/security/final_10nodes/`** comme résultats finaux, pas V2 ni les smokes 120 s.

Corrections **obligatoires de code/science** avant soutenance : **aucune**.  
Actions **fortement recommandées** (organisation / confusion jury) : section 18–19.

---

## 1. Compilation

**Commande :**

```bash
cd /home/opp_env
opp_env run omnetpp-6.3.0 inet-4.5.4 flora-1.2.0 --isolated -c \
  'cd /home/opp_env/AgriLoRaSec && make -j4'
```

**Résultat :** `cd src && make` → `Nothing to be done for 'all'.` Exit 0.  
**Erreurs :** aucune.  
**Warnings :** aucun affiché (rebuild incrémental, sources déjà à jour).

Binaire attendu par les campagnes : `out/clang-release/src/AgriLoRaSec`.

**BUILD: PASS**

---

## 2. Architecture LoRa

### Réseau 10 nœuds

`simulations/package.ned` réseau `AgriLoRaNetwork` :

| Élément | Preuve |
|---|---|
| 10 nœuds | `loRaNode0` … `loRaNode9` (L59–89), `numberOfNodes = default(10)` |
| Gateway | `loRaGW[]: AgriLoRaGW` (L54–56) |
| Medium | `LoRaMedium` (L45–47) |
| Logger | `packetEventLogger: PacketEventLogger` (L48–50) |
| Jammer / Replay / Wormhole | `jammer`, `replayer`, `wormholeA`, `wormholeB` (L91–107) |
| Backhaul | Ethernet GW → InternetCloud → NetworkServer |

`src/AgriLoRaGW.ned` : `LoRaGWNic` FLoRa + `LoggingPacketForwarder` (L95–99, connexions L128–129).  
INI : `**.loRaNode*.app[0].typename = "agrilorasec.AgriSensorApp"` (`omnetpp.ini` L81). MAC nœuds légitimes = FLoRa `LoRaMac` (non forké). Radio = `LoRaRadio`.

### Scalabilité 20 / 30 / 50

NED : `AgriLoRaNetwork20.ned` (`loRaNode0`–`19`), `AgriLoRaNetwork30.ned` (`0`–`29`), `AgriLoRaNetwork50.ned` (`0`–`49`).  
INI : `[Config Nodes20/30/50]` + `NoAttackN` / `JammingN` / `ReplayN` / `WormholeN`.  
Campagne réelle : `ml/v3/run_campaign_v3.py` `SIZES = [10, 20, 30, 50]`, `CONFIG_BY_N` (L33–39). Datasets 2880 lignes × 4 tailles.

**NETWORK ARCHITECTURE: PASS**

---

## 3. Configuration LoRa

Fichier principal : `simulations/omnetpp.ini`.

| Paramètre | Valeur | Lignes |
|---|---|---|
| Fréquence | `868MHz` (défaut NED apps) | `src/AgriSensorApp.ned` L37, `JammerApp.ned` L22, `ReplayApp.ned` L23, `WormholeApp.ned` L25 |
| Bande passante | `125 kHz` | `omnetpp.ini` L77 |
| Puissance TX | `14dBm` | L76 |
| Coding rate | `4` | L78 |
| SF défaut Qtenv | `12` | L75 |
| SF campagne | 7–12 via `--initialLoRaSF` | `run_campaign_v3.py` `SFS = [7,8,9,10,11,12]` |
| Propagation | `LoRaLogNormalShadowing` | `omnetpp.ini` L135 |
| `sigma` | `3.57` | L130 |
| Durée défaut INI | `sim-time-limit = 30min` | L33 |
| Durée campagnes | `1800s` override | `run_campaign_v3.py` L29 ; `run_security_final_10.py` L31 |
| Seeds | `[0,1,2,3]` + `--seed-set=` | `run_campaign_v3.py` L30, L114 |
| Trafic capteurs | `exponential(50s)` | `omnetpp.ini` L38–39 |
| Neighbor cache | `546m` | L142 |
| Zone | `1000m × 1000m` | L49–54 |
| ADR nœud | `false` | L79 |

Commentaire INI L73–74 encore « `generate_packet_dataset.py` » : **obsolète** (campagnes = `run_campaign_v3.py`). Ne change pas les runs.

**LORA CONFIGURATION: PASS** (WARNING mineur : commentaire INI + `sim-time-limit` 30 min vs 1800 s campagne)

---

## 4. Jamming

Implémentation : `src/JammerApp.cc` / `.ned`, nœud `src/JammerNode.ned` (`JammerLoRaNic` → `JammerSafeLoRaMac` + radio LoRa).

- Activation : `[Config Jamming]` `**.jammer.numApps = 1`, `typename = JammerApp` (`omnetpp.ini` L156–171).
- `timeToFirstPacket = 0s`, `timeToNextPacket = 0.05s` (L163–164) **après** airtime PHY + fenêtres MAC FLoRa (`floraPostTxMacWindowsS`, `JammerApp.cc` L145–159).
- Fenêtre attaque : `360s`–`1440s` (L165–166).
- Pile LoRa : `send(pktRequest, "socketOut")` (`JammerApp.cc` L171–202) → NIC → radio.
- Collisions : FLoRa collision si même `loRaCF`. Campagne : collisions moyennes **131.167** BEFORE vs **4.875** AFTER hop (recalcul CSV). Log `JammingProtected_sf7_s0.log` : `CHANNEL_HOP applied` ×10, `JammerApp SEND` ×8367, fin `t=1800s`.

**JAMMING ATTACK: PASS**

---

## 5. Replay RAW

Chemin réel :

1. Capture RF `signalAddedSignal` (`ReplayApp.cc` L250–258, L291–372)  
2. Copie à partir du chunk MAC (pas un nouveau `LoRaAppPacket` d’identité attaquant) L346–347  
3. `ReplayLoRaNic` (`src/ReplayNode.ned` L10–22) `mac.typename = PreserveHeaderLoRaMac`  
4. `PreserveHeaderLoRaMac::encapsulate` skip si `REPLAY_RAW_KIND` + `LoRaMacFrame` déjà en tête (`PreserveHeaderLoRaMac.cc` L19–31)  
5. Retransmission `send(replay, "socketOut")` (`ReplayApp.cc` L402–424)

Preuve conservation MAC/seq : log `ReplayProtected_sf12_s3.log` — `PreserveHeaderLoRaMac skip` 50, `ReplayApp REPLAY` 50, `GW_DUP_REJECT` 32. CSV paquets : `sender_name=replayer` avec `sender_mac` d’un nœud légitime et `seq_seen_before=1` (ex. `ReplayProtected_sf11_s1.csv`).

INI Replay : `timeToReplay = uniform(4s, 25s)`, `PreserveHeaderLoRaMac` L186, attaque 360–1440.

**REPLAY RAW ATTACK: PASS**

---

## 6. Wormhole

`wormholeA` rôle `entry`, `wormholeB` `WormholeExitNode` + `ReplayLoRaNic` (`package.ned` L101–107, `WormholeNode.ned` / `ReplayNode.ned`).  
INI : `peerAppPath`, `tunnelDelay = uniform(0.05s, 6s)`, MAC PreserveHeader sur **exit** (`omnetpp.ini` L192–220).  
Logs : `WormholeApp TUNNEL A->B` (`WormholeApp.cc` L413), `EXIT TX` (L474), `send(pkt, "socketOut")` (L491).  
CSV : `sender_name=wormholeB` + MAC victime + `seq_seen_before=1` (ex. `WormholeProtected_sf12_s3.csv`).

**Cohérence étoile :** LoRa FLoRa est **star / 1-hop vers GW**. Ce n’est **pas** un wormhole de routage multi-saut (pas de raccourci AODV). C’est un **relais RAW** Entry→tunnel applicatif→Exit→GW, qui crée un **doublon (MAC, seq)** à la gateway. C’est cohérent avec la topologie **si** on le présente ainsi. Un jury AODV/MANET peut le contester comme « vrai wormhole ».

**WORMHOLE ATTACK: PASS** (caveat scientifique : relais RAW en étoile, pas wormhole multi-hop)

---

## 7. Logger et dataset

`src/PacketEventLogger.cc` en-tête CSV L45–47 :

`packet_id, recv_time_s, sender_mac, sender_name, receiver_id, rssi_dBm, snir_dB, packet_size_B, transmitted_bytes, energy_consumed, sequence_number, spreading_factor, tx_power_dBm, coding_rate, seq_seen_before, interarrival_s, collision, received, Label`

- `seed` : **absent du logger** ; reconstruit depuis le nom de fichier (`_s{seed}`) dans `build_dataset_v2.py` / `build_dataset_v3.py`.  
- Label logger : `labelFromActiveConfig()` L50–61 — sous-chaîne `Jamming` / `Replay` / `Wormhole`. Donc `JammingProtected` → label **Jamming**. Les datasets V2/V3 n’incluent pas les configs Protected.  
- Source : `LoggingPacketForwarder::tryLogReception` → `logGatewayReception` ; collisions via signal `LoRaReceptionCollision`.

Datasets fenêtres : features radio agrégées, pas identité. `seed` / `SF` / `run_id` = métadonnées.

**LOGGER/DATASET: PASS** (seed hors CSV paquet ; NaN RSSI/SNIR si fenêtre sans RX — imputés au ML)

---

## 8. Dataset V2 (et V3, pour ne pas confondre)

Comptages **réels** (`csv.DictReader`) :

| Fichier | Lignes | Runs | Labels | SF | Seeds | Doublons lignes |
|---|---|---|---|---|---|---|
| `ml/v2/features/dataset_v2_10nodes.csv` | 2880 | 96 | 720×4 | 7–12 | 0–3 | 0 |
| `dataset_v2_20nodes.csv` | 2880 | 96 | 720×4 | 7–12 | 0–3 | 0 |
| `dataset_v2_30nodes.csv` | 2880 | 96 | 720×4 | 7–12 | 0–3 | 0 |
| `dataset_v2_50nodes.csv` | 2880 | 96 | 720×4 | 7–12 | 0–3 | 0 |
| `dataset_v2_all_nodes.csv` | 11520 | 384 | 2880×4 | 7–12 | 0–3 | 0 |
| `ml/v3/features/dataset_v3_*` | **mêmes 2880 / 11520** | 96 / 384 | **Normal 1584 + 432×3 attaques** par taille | 7–12 | 0–3 | 0 |

Fenêtres : longueur **60.0 s** partout (V2 et V3). 30 fenêtres/run × 96 = 2880.

**Différence V2 vs V3 (critique soutenance) :**  
- V2 : Label = **scénario du run entier** (les fenêtres 0–360 s d’un run Jamming sont quand même `Jamming`).  
- V3 : `scheduled_label` (`build_dataset_v3.py` L99–107) : attaque seulement sur `[360, 1440)`, sinon `Normal`. D’où 1584 Normal vs 720 V2.

NaN : ~13–14 % des fenêtres 10 nœuds sans RSSI (aucune RX) — pas une corruption, des fenêtres vides. Imputation `SimpleImputer` dans `train_eval_v3.py`.

**DATASET V2: PASS**  
V3 également PASS et **scientifiquement préférable** pour le ML.

---

## 9. Machine learning

Modèles présents (fichiers) :

| | RF | XGB | ANN/MLP | LSTM |
|---|---|---|---|---|
| Script V3 | `ml/v3/ml/train_eval_v3.py` | idem | `MLPClassifier` 64→32 | `lstm_*.pt` |
| Script V2 | `ml/v2/ml/train_eval_v2.py` | idem | idem | idem |
| Artefacts | `ml/v{2,3}/ml/models/{rf,xgb,ann}_{10,20,30,50,gen}.joblib` + `lstm_*.pt` + `preproc_*.joblib` | | | |

**X (V3 L62–77) :** 14 features agrégées (`packet_rate` … `interarrival_std`).  
**Y :** `Label`.  
**Split :** `train_test_split` sur `run_id` stratifié par **scénario du run**, pas par Label de fenêtre (L186–193).  
**Anti-fuite :** `FORBIDDEN_IN_X` (MAC, seq, Label, seed, SF, sender_name, …) + `leakage_check`.  
**Métriques :** accuracy, P/R/F1 macro, matrices de confusion, `ml_v3_summary.json`, `scalability_table.csv`.

V2 F1 ~0.42–0.48 vs V3 LSTM F1 ~0.80–0.83 : **V2 n’est pas le résultat ML à montrer**. Ce n’est pas un bug de fuite, c’est le labeling run-entier.

Scripts racine `ml/train_*.py`, `ml/ml_common.py` (Label parfois dérivé de `sender_name`) = **pipeline ancien**, pas V3.

**ML PIPELINE: PASS** (WARNING : présenter uniquement V3)

---

## 10. Scalabilité

- Configs INI `Nodes20/30/50` réellement utilisées par `CONFIG_BY_N`.  
- Datasets V3 10/20/30/50.  
- Table : `ml/v3/ml/reports/scalability_table.csv` (16 lignes RF/XGB/ANN/LSTM × 4 N).  
- Graphiques : `accuracy_vs_nodes.png`, `macro_f1_vs_nodes.png` (18 sept. 2026).  
- Générateur : `plot_scalability_curves_v3.py` lit **uniquement** ce CSV (`REPORTS / scalability_table.csv`). `train_eval_v3.py` `plot_scalability()` L545+.

Extrait V3 Macro-F1 : LSTM 0.8336 / 0.7982 / 0.7956 / 0.7972 ; RF 0.7688 / 0.7661 / 0.7730 / 0.7281.

Courbes V2 (`ml/v2/ml/reports/`) existent encore (~0.42) : **ne pas les projeter comme résultat final**.

**SCALABILITY: PASS**

---

## 11. Sécurité Jamming

Code hop : `AgriSensorApp.cc` L57–65, L227–235 `setCF(channelHopFrequency)` à `channelHopTime`.  
INI `[Config JammingProtected]` L373–378 : `enableChannelHop=true`, `360s`, `868.3MHz`. Jammer **reste** à 868.0 MHz.  
GW `iAmGateway=true` : reçoit plusieurs CF ; FLoRa collide seulement si même CF → les collisions chutent, le jammer peut encore être **décodé** à la GW.

Campagne : `ml/security/final_10nodes/` 24 runs BEFORE (V3 réutilisés) + 24 AFTER, tous `SimOk=True`.

**Recalcul `security_10nodes_detailed.csv` (n=24) :**

| | Collisions | PDR |
|---|---|---|
| BEFORE | **131.167 ± 25.26** | **0.307099 ± 0.182** |
| AFTER | **4.875 ± 3.392** | **0.450261 ± 0.306** |

Attendu rapport ≈ 131.2 / 4.88 / 0.307 / 0.450 : **conforme**.  
`CHANNEL_HOP applied` ×10 nœuds dans un log AFTER SF7.

PDR AFTER ≈ PDR Normal (0.453) : le hop restaure un canal proche du sain. Le jammer n’est pas « éteint ».

**JAMMING SECURITY: PASS**

---

## 12. Sécurité Replay

Filtre : `LoggingPacketForwarder.cc` L16, L64–77 `seenMacSeq` clé `mac#seq`, L124–133 `GW_DUP_REJECT` + `delete pkt`.  
BEFORE : `enableDuplicateFilter` défaut false ; AFTER : `[Config ReplayProtected]` L380–383 `true`.  
Mémoire first-seen : le **premier** (original ou copie) est accepté ; le second est rejeté.

**Recalcul n=24 Replay AFTER :**

| Métrique | Moyenne |
|---|---|
| RAW TX (`ReplayApp REPLAY`) | 111.708 |
| RAW RX (`sender_name=replayer`) | 41.708 |
| True duplicate pairs (même MAC+seq, ≥2 RX PHY) | 23.958 |
| Duplicate rejected | **23.958** |
| Taux rejet si paire détectée | 100 % |
| DuplicateAccepted (copie RX − rejects) | 17.75 |

Les **17.75** ne contredisent pas le filtre : ce sont des copies arrivées **sans** original décodé (first-seen = copie). À dire au jury.

BEFORE : rejected = 0, pairs ≈ 23.375 acceptées.

**REPLAY SECURITY: PASS**

---

## 13. Sécurité Wormhole

Même filtre GW. Config `WormholeProtected` L385–388.

**Recalcul n=24 Wormhole AFTER :**

| Métrique | Moyenne |
|---|---|
| EXIT TX | 121.375 |
| EXIT RX GW | 43.625 |
| True duplicate pairs | 22.167 |
| Duplicate rejected | **22.167** |

Attendu ≈ 22.17 : **conforme**. BEFORE rejected = 0.

**WORMHOLE SECURITY: PASS**

---

## 14. Faux positifs

24 runs Normal BEFORE (`NoAttack` V3) + 24 AFTER (`NoAttackProtected` hop+filtre). Tous `SimOk=True`.

`FalseRejects` moyen = **0.0** (écart-type 0) BEFORE et AFTER.  
PDR/collisions Normal AFTER **identiques** à BEFORE (mêmes seeds ; hop sans jammer + GW multi-CF). Scientifiquement attendu, pas une erreur de copie de tableau.

Logs `NoAttackProtected_*_security.csv` : actions `accept` / `first_mac_seq`, pas de `reject` sur ce contrôle.

**FALSE POSITIVE TEST: PASS**

---

## 15. BEFORE vs AFTER

`run_security_final_10.py` :

- Réseau 10 nœuds, `SIM_TIME=1800s`, `SFS=7..12`, `SEEDS=0..3`.  
- BEFORE = **copie** `ml/v3/raw/10nodes/` (même attaque, positions display-string, radio).  
- AFTER = configs `*Protected` uniquement (hop **ou** filtre).  
- 192 lignes detailed = 4 attaques × 2 × 24.

Différence volontaire : protection.  
Non identique à 100 % des TX Replay/Wormhole AFTER vs BEFORE (stochasticité interne attaquant + hop/filtre) : écarts ~1 paquet — acceptable.

**BEFORE/AFTER VALIDITY: PASS**

---

## 16. Résultats et figures

Présents et datés :

- Sécurité (23 sept. 16:41) :  
  `ml/security/final_10nodes/figures/`  
  `jamming_{collisions,pdr}_by_sf.png`, `replay_{copy_rx,detected,rejected}_by_sf.png`, `wormhole_{copy_rx,detected,rejected}_by_sf.png`, `normal_{pdr,false_rejects}_by_sf.png`  
  Tables : `security_10nodes_detailed.csv` (192), `security_10nodes_summary.csv` (8)  
  Rapport : `reports/security_10nodes_final_report.md`
- ML V3 : `scalability_table.csv`, PNG accuracy/macro-F1, `ml_v3_summary.json`, confusion matrices.
- ML V2 : mêmes noms de PNG, scores ~0.42 — **risque de confusion**.

Autres dossiers pouvant tromper : `ml/security/eval/`, smokes, `ml/generate_packet_dataset.py`, backups `backup_before_*`.

**RESULTS/FIGURES: PASS** (WARNING : cohabitation V2/V3/smoke)

---

## 17. Reproductibilité

Documenté **dans le code** (chemins absolus `/home/opp_env/AgriLoRaSec`) :

| Étape | Script / commande |
|---|---|
| Compile | `opp_env run … make` (section 1) |
| Normal / attaques | `opp_run` `-c NoAttack\|Jamming\|Replay\|Wormhole` + SF/seed |
| Dataset V3 | `ml/v3/run_campaign_v3.py` puis `build_dataset_v3.py` |
| ML V3 | `ml/v3/ml/train_eval_v3.py` (venv `ml/v2/ml/.venv`) |
| Scalabilité plots | `plot_scalability_curves_v3.py` |
| Sécurité 10 nœuds | `ml/security/final_10nodes/run_security_final_10.py` |

**Blocages pour un tiers :**

1. Git `main` **ne contient pas** `ml/security/` ni les `*Protected` INI (fichiers `M` / `??` au 23 sept.). Clone GitHub ≠ machine locale.  
2. Chemins WSL `opp_env`, INET/FLoRa relatifs `../../flora-1.2.0`.  
3. Campagnes lourdes (384 × 1800 s) ; les CSV V3 sont le moyen de reproduire le ML sans resimuler.  
4. `simulations/results/` gitignored / pollué par les derniers Protected.

Une personne **avec cette machine WSL** peut suivre les scripts. Un clone GitHub seul **ne reproduit pas** la campagne sécurité.

**REPRODUCIBILITY: WARNING**

---

## 18. Organisation (rien n’a été supprimé)

| À conserver (soutenance) | À archiver plus tard (hors slide) |
|---|---|
| `src/`, `simulations/omnetpp.ini` + NED 10/20/30/50 | `backup_before_replay`, `backup_before_wormhole`, `backup_before_attack_timing_v2`, `backup_before_security`, `backup_before_security_final_10nodes`, `avant_scalability_30_50` |
| `ml/v3/` features + models + reports | `ml/v2/` (historique scientifique, ne pas projeter) |
| `ml/security/final_10nodes/` | `ml/security/` smoke/eval 400 s / 120 s |
| `FINAL_PROJECT_AUDIT.md`, guides soutenance | `ml/train_*.py`, `generate_packet_dataset.py` (V1) |
| | `simulations/results/` CSV Protected mélangés au dernier run |
| | `.venv` (~1.3 G), raw OMNeT gitignored |

**PROJECT ORGANIZATION: WARNING**

---

## 19. Risques jury

| Gravité | Problème |
|---|---|
| **CRITICAL** | Présenter les PNG/scores **V2** (~F1 0.42) comme résultat final. Le vrai ML est **V3**. |
| **CRITICAL** | Confondre smoke 120 s / eval 400 s (0 reject Replay court) avec la campagne **1800 s** (`final_10nodes`). |
| **MAJOR** | GitHub/local divergents : sécurité non commitée. Si le jury clone le dépôt, le code hop/filtre et les CSV manquent. |
| **MAJOR** | Wormhole = relais RAW en **étoile**, pas un tunnel de routage. À assumer en une phrase. |
| **MAJOR** | Filtre first-seen : copies sans original **acceptées** (~17.8 Replay / ~21.5 Wormhole « DuplicateAccepted »). Ce n’est pas 100 % des copies TX. |
| **MAJOR** | `labelFromActiveConfig` : `JammingProtected` ⊆ `Jamming`. Ne pas mélanger Protected dans un dataset ML. |
| **MINOR** | Commentaire INI `generate_packet_dataset.py` ; `sim-time-limit=30min` vs override 1800 s. |
| **MINOR** | Chemins absolus `/home/opp_env/AgriLoRaSec` dans les scripts Python. |
| **MINOR** | `neighborCache.range=546m` vs aire 1000 m ; `energyDetection=-110 dBm` vs RSSI souvent &lt; −120 dBm (pertes FLoRa réelles). |
| **MINOR** | Colonne `AttackCopyTX` jamming = paquets jammer, pas des copies RAW. |
| **MINOR** | Seed absent du CSV logger. |
| **INFORMATION** | Normal AFTER CSV identique à BEFORE (hop inutile sans jammer). |
| **INFORMATION** | `PreserveHeaderLoRaMac` / `ReplayLoRaNic` : copies NED locales, FLoRa non forkée. |
| **INFORMATION** | Backups multiples dans l’arbre source. |

Code mort / anciennes implémentations Replay : dossiers `backup_before_replay` etc. Le code **actif** est `src/ReplayApp.cc` + PreserveHeader.

---

## 20. Tableau récapitulatif

| Component | Status | Evidence | Problem | Action required |
|---|---|---|---|---|
| Build | PASS | `make -j4` nothing to be done, exit 0 | Rebuild incrémental sans liste de warnings | Aucune |
| LoRa network | PASS | NED 10/20/30/50, AgriLoRaGW, AgriSensorApp | — | Aucune |
| Jamming | PASS | JammerApp + INI 0s/0.05s + collisions 131→4.9 | Jammer encore RX à la GW après hop | Expliquer CF collision FLoRa |
| Replay | PASS | Capture→ReplayLoRaNic→PreserveHeader ; logs skip MAC/seq | — | Aucune |
| Wormhole | PASS | Entry tunnel Exit RAW ; CSV wormholeB + MAC victime | Pas un wormhole multi-hop | Phrase de cadrage |
| Logger | PASS | PacketEventLogger header L45–47 | Pas de colonne seed | Aucune |
| Dataset | PASS | V2 et V3 : 2880×4 + 11520, W=60, 0 doublons | V2 labels run-entier | Montrer V3 pour le ML |
| ML | PASS | RF/XGB/ANN/LSTM V3, split run, FORBIDDEN_IN_X | Scripts V1 à la racine `ml/` | Slides = V3 uniquement |
| Scalability | PASS | table CSV → PNG V3 | PNG V2 homonymes | Citer `ml/v3/ml/reports/` |
| Jamming security | PASS | Recalc 131.167 / 4.875 / 0.307 / 0.450 | Hop nœuds seulement | Aucune |
| Replay security | PASS | Recalc reject 23.958 = pairs | Copies first-seen acceptées | Dire le taux « si doublon PHY » |
| Wormhole security | PASS | Recalc reject 22.167 | Idem | Idem |
| False positives | PASS | FalseRejects=0, n=24+24 | — | Aucune |
| BEFORE/AFTER | PASS | V3 reuse + Protected, 192/192 SimOk | TX attaque ±1 | Aucune |
| Results | PASS | figures 23/09 16:41 + summary CSV | V2/smoke/backups | Ranger visuellement |
| Reproducibility | WARNING | scripts locaux complets | Git sans sécurité ; chemins WSL | Commit/push **après** GO GIT ; ne pas prétendre que GitHub = tout |

---

## TECHNICALLY READY FOR DEFENSE: YES

### Corrections obligatoires (science)

Aucune. Ne pas retoucher attaques, datasets, ni chiffres pour « faire plus joli ».

### Améliorations facultatives (après l’audit)

1. Commit + push `src` sécurité, `omnetpp.ini` Protected, `ml/security/final_10nodes/` (hors raw énormes si GitHub 100 Mo) — seulement si vous le demandez (`GO GIT`).  
2. Archiver les `backup_*` hors de l’arbre montré à l’encadrante (`GO CLEANUP`).  
3. Corriger le commentaire INI L73–74.  
4. Une slide « ce que le wormhole est / n’est pas ».  
5. Une slide « first-seen : original perdu ⇒ copie acceptée ».

### Règle de présentation

**Source de vérité soutenance :**  
- Réseau / attaques : `src/` + `simulations/omnetpp.ini`  
- ML / scalabilité : `ml/v3/`  
- Sécurité 10 nœuds : `ml/security/final_10nodes/`
