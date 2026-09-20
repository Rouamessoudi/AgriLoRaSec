# Guide de soutenance — scalabilité AgriLoRaSec V3

Document de révision. Aucune simulation ni entraînement n’est relancé ici.
Tous les extraits sont tirés du code réel du projet.

Chemin projet : `/home/opp_env/AgriLoRaSec`

---

# PARTIE 0 — Avant / après

## OBJECTIF

Montrer que le réseau **10 nœuds existait déjà**, et que la scalabilité a consisté à **ajouter des réseaux séparés** 20 / 30 / 50, pas à écraser le 10.

## AVANT (10 nodes)

Réseau unique dans `simulations/package.ned` :

```ned
network AgriLoRaNetwork
{
    parameters:
        int numberOfNodes = default(10);
        int sensorsPerNode = default(3);
```

Dix capteurs `loRaNode0` … `loRaNode9`, une gateway `loRaGW[]`, `packetEventLogger`, jammer, replayer, wormholeA/B.

Configuration : `[Config NoAttack]`, `[Config Jamming]`, `[Config Replay]`, `[Config Wormhole]` dans `simulations/omnetpp.ini`.

## APRÈS (10 + 20 + 30 + 50)

Trois **nouveaux** fichiers NED. Le réseau 10 n’a pas été remplacé.

| Fichier | Créé ou modifié | Pourquoi | Rôle |
|---|---|---|---|
| `simulations/package.ned` | **Existant** (réseau 10) | Base | `AgriLoRaNetwork` : 10 LoRaNodes |
| `simulations/AgriLoRaNetwork20.ned` | **Créé** | Ajouter 20 nœuds sans toucher au 10 | `network AgriLoRaNetwork20` |
| `simulations/AgriLoRaNetwork30.ned` | **Créé** | Idem 30 | `network AgriLoRaNetwork30` |
| `simulations/AgriLoRaNetwork50.ned` | **Créé** | Idem 50 | `network AgriLoRaNetwork50` |
| `simulations/omnetpp.ini` | **Modifié** | Brancher les nouveaux réseaux + héritage des attaques | `Nodes20/30/50`, `NoAttack20` … `Wormhole50` |
| `ml/v3/run_campaign_v3.py` | **Créé** (campagne V3) | 384 runs | Boucles N × scénario × SF × seed |
| `ml/v3/build_dataset_v3.py` | **Créé** | Fenêtres W=60, labels 360–1440 | RAW → CSV features |
| `ml/v3/ml/train_eval_v3.py` | **Créé** | ML + courbes | RF/XGB/ANN/LSTM × 10/20/30/50 |
| `src/ReplayApp.cc`, `WormholeApp.cc`, `JammerApp.cc`, `PreserveHeaderLoRaMac.cc` | **Non retouchés** pour la scalabilité | Même politique d’attaque | Attaques V3 |
| FLoRa (`flora-1.2.0`) | **Non modifié** | Contrainte scientifique | PHY/MAC LoRa |

## CE QUE JE DIS À LA PROF

« On n’a pas agrandi le réseau 10 nœuds en place. On a créé trois NED séparés qui recopient les positions 0–9, puis on ajoute des nœuds. Les configs INI font `extends` des attaques déjà validées. »

---

# PARTIE 1 — 20 nodes (`AgriLoRaNetwork20.ned`)

## OBJECTIF

Comprendre comment 20 LoRaNodes sont **déclarés**, **positionnés**, et **reliés** à la gateway.

## FICHIER

`simulations/AgriLoRaNetwork20.ned`

## CODE — paramètres

```ned
network AgriLoRaNetwork20
{
    parameters:
        int numberOfNodes = default(20);
        int numberOfGateways = default(1);
        int sensorsPerNode = default(3);
        @display("bgb=780,700");
```

- `numberOfNodes` : paramètre (documentation / INI). **Ce n’est pas lui qui crée les nœuds.**
- `sensorsPerNode = 3` : **3 mesures par nœud** (température, sol, air) dans **un** paquet LoRa (`AgriSensorApp::sendSensorReading`). 20 nodes ≠ 60 « nœuds radio ».
- `bgb=780,700` : **même zone** que le réseau 10.

## CODE — infrastructure (identique au 10)

```ned
        LoRaMedium: LoRaMedium { ... }
        packetEventLogger: PacketEventLogger { ... }
        loRaGW[numberOfGateways]: AgriLoRaGW {
            @display("p=375,356;is=s");
        }
```

- `LoRaMedium` : canal radio. Les nœuds **n’ont pas de câble vers la GW**. Ils émettent dans le medium LoRa.
- `loRaGW[0]` : gateway FLoRa/AgriLoRaSec.
- `packetEventLogger` : écrit le CSV RAW.

Les `connections` filaires ne concernent **que** NS ↔ internet ↔ routeur ↔ **gateway Ethernet** :

```ned
    connections:
        networkServer.ethg++ <--> Eth1G <--> nsRouter.ethg++;
        ...
            gwRouter[i].ethg++ <--> Eth1G <--> loRaGW[i].ethg++;
```

**Aucun** `loRaNodeX` n’apparaît dans `connections`. Communication nœud → GW = **radio LoRa** via `LoRaMedium`.

## CODE — 10 premiers nœuds (copies du 10)

Positions **identiques** à `package.ned`, ex. `loRaNode0` `p=100,534`.

Pourquoi `loRaNode0`, `loRaNode1`, … et pas un tableau `loRaNode[20]` ?  
Parce que chaque nœud a une **position `@display` différente**. Un vecteur NED aurait les mêmes coordonnées par défaut.

## CODE — nœuds ajoutés 10–19

```ned
        loRaNode10: LoRaNode { @display("p=175,500;..."); }
        ...
        loRaNode19: LoRaNode { @display("p=280,470;..."); }
```

C’est **ça** le passage 10 → 20 : dix sous-modules **en plus**, même zone.

## CODE — attaquants (mêmes positions que le 10)

```ned
        jammer: JammerNode { @display("p=649,194;..."); }
        replayer: ReplayNode { @display("p=648,429;..."); }
        wormholeA: LoRaNode { @display("p=100,298;..."); }
        wormholeB: WormholeExitNode { @display("p=649,311;..."); }
```

Ils ne comptent **pas** dans les 20 LoRaNodes agricoles.

## EXEMPLE CONCRET

`loRaNode19` existe seulement dans 20/30/50. Dans le 10, le dernier capteur est `loRaNode9`.

## ORAL 30 s — « Comment êtes-vous passés de 10 à 20 nodes ? »

« Nous n’avons pas modifié le NED à 10 nœuds. Nous avons créé `AgriLoRaNetwork20.ned` : mêmes 10 positions, plus `loRaNode10` à `loRaNode19` dans la même zone. La gateway, le logger et les attaquants sont recopiés. Dans `omnetpp.ini`, `NoAttack20` fait `extends = NoAttack, Nodes20` : on change le réseau, pas la politique d’attaque. »

## QUESTION PROF

« Pourquoi ne pas faire `loRaNode[20]` ? »  
Parce que chaque nœud a une position géographique distincte dans le NED. `numberOfNodes` seul ne crée pas ces modules.

---

# PARTIE 2 — 30 et 50 nodes

## 10 → 20

Ajout : `loRaNode10` … `loRaNode19`.

## 20 → 30 — fichier `AgriLoRaNetwork30.ned`

Commentaire réel : « Positions 0-19 inchangees vs 10/20. »

Ajout :

```ned
        loRaNode20: LoRaNode { @display("p=130,560;..."); }
        ...
        loRaNode29: LoRaNode { @display("p=670,560;..."); }
```

Exemple : `loRaNode19` (déjà en 20) vs `loRaNode20` (nouveau en 30).

## 30 → 50 — fichier `AgriLoRaNetwork50.ned`

Ajout `loRaNode30` … `loRaNode49` :

```ned
        loRaNode30: LoRaNode { @display("p=115,490;..."); }
        ...
        loRaNode49: LoRaNode { @display("p=85,500;..."); }
```

## 50 NODES ≠ 50 capteurs

- **50 nodes** = 50 modules `LoRaNode` = 50 radios / 50 applications `AgriSensorApp`.
- Chaque app envoie **un paquet** contenant **3 mesures** (`sendSensorReading` dans `src/AgriSensorApp.cc`).
- `sensorsPerNode = 3` documente cela. Ce n’est pas une boucle qui crée 3 radios.

Oral : « On scale le nombre d’émetteurs LoRa, pas le nombre de grandeurs dans le payload. »

---

# PARTIE 3 — `omnetpp.ini`

## OBJECTIF

Ne pas recopier Jamming/Replay/Wormhole quatre fois. Utiliser **`extends`**.

## CODE — attaques de base (10 nœuds, héritées)

```ini
[Config Jamming]
**.jammer.numApps = 1
**.jammer.app[0].attackStart = 360s
**.jammer.app[0].attackEnd = 1440s
```

Même chose pour Replay et Wormhole (`timeToReplay`, `tunnelDelay`, `maxPending*`).

## CODE — couche « taille »

```ini
[Config Nodes20]
network = agrilorasec.simulations.AgriLoRaNetwork20
**.numberOfNodes = 20
**.loRaNode10.**.initFromDisplayString = true
...
**.loRaNode19.**.initFromDisplayString = true
```

`initFromDisplayString` : la position vient du `@display` du NED (comme les nœuds 0–9 déjà activés en General).

## CODE — scénarios 20 (le motif se répète en 30 et 50)

```ini
[Config NoAttack20]
extends = NoAttack, Nodes20

[Config Jamming20]
extends = Jamming, Nodes20

[Config Replay20]
extends = Replay, Nodes20

[Config Wormhole20]
extends = Wormhole, Nodes20
**.wormholeA.app[0].peerAppPath = "AgriLoRaNetwork20.wormholeB.app[0]"
```

`extends` = union des paramètres. Seul le **chemin du tunnel** wormhole change (`AgriLoRaNetwork` vs `AgriLoRaNetwork20/30/50`), parce que le nom du module réseau change.

General : `network = AgriLoRaNetwork`, `sim-time-limit = 30min`, `**.loRaNode*.app[0].timeToNextPacket = exponential(50s)`.

## ORAL

« Les attaques sont définies une fois. `Jamming50` étend `Jamming` et `Nodes50`. On ne retune pas le jammer selon N. »

---

# PARTIE 4 — `run_campaign_v3.py` (384 runs)

## CONSTANTES

```python
SIM_TIME = os.environ.get("V3_SIM_TIME", "1800s")
SEEDS = [0, 1, 2, 3]
SFS = [7, 8, 9, 10, 11, 12]
SCENARIOS = ["Normal", "Jamming", "Replay", "Wormhole"]
SIZES = [10, 20, 30, 50]
```

`CONFIG_BY_N[20]["Replay"]` = `"Replay20"`.

## BOUCLE (le cœur)

```python
def all_jobs():
    jobs = []
    for n in SIZES:          # 4
        for sc in SCENARIOS: # 4
            for sf in SFS:   # 6
                for seed in SEEDS:  # 4
                    jobs.append(job_paths(n, sc, sf, seed))
    return jobs
```

4 × 4 × 6 × 4 = **384**.

## EXEMPLE : N=20, Replay, SF=9, seed=2

1. Config OMNeT : `Replay20` (`stem_for` → `Replay20_sf9_s2`).
2. Réseau NED : `AgriLoRaNetwork20` (via `Nodes20`).
3. Commande (construite dans `run_job`) :

```text
AgriLoRaSec -u Cmdenv -c Replay20
  --sim-time-limit=1800s
  --seed-set=2
  --**.packetEventLogger.outputFile="results/Replay20_sf9_s2.csv"
  --**.loRaNode*.app[0].initialLoRaSF=9
  (idem jammer, replayer, wormholeA/B)
```

cwd = `simulations/`.

4. Copie : `simulations/results/Replay20_sf9_s2.csv` → `ml/v3/raw/20nodes/Replay20_sf9_s2.csv`.

Succès exigé : `Simulation time limit reached -- at t=1800s` et pas de `Error:`.

---

# PARTIE 5 — Pourquoi le RAW augmente

Chaîne réelle :

1. `AgriSensorApp::sendSensorReading` — 3 capteurs, 1 `Packet`.
2. LoRaMac / radio FLoRa — TX dans `LoRaMedium`.
3. `loRaGW` reçoit (ou collision).
4. `LoggingPacketForwarder::handleMessage` sur `lowerLayerIn` appelle `tryLogReception`.
5. `PacketEventLogger::logGatewayReception` puis `writeRxRow` → une ligne CSV.
6. Collisions : signal `LoRaReceptionCollision` → `logCollisionIfGateway` si le chemin contient `loRaGW`.

Plus de nœuds → plus de TX → plus de RX et de collisions → plus de lignes RAW.

Chiffres campagne : 111 386 (10) → 137 862 (20) → 163 053 (30) → 215 742 (50). Collisions GW : 3 844 → 27 142.

Les 2880 lignes ML : voir partie 6 (fenêtrage temporel).

---

# PARTIE 6 — `build_dataset_v3.py`

## Pipeline

RAW CSV → garder RX décodées + collisions GW (`classify_raw_row`) → découper [0, 1800) en pas de 60 s → 14 features + Label.

```python
WINDOW_S = 60.0
n_windows = int(math.floor(sim_end / WINDOW_S + 1e-12))  # 30
for i in range(n_windows):
    t0 = i * WINDOW_S
    t1 = t0 + WINDOW_S
    label = scheduled_label(scenario, t0, t1)
    D_rows = [r for r in decoded if t0 <= t < t1]
    C_rows = [r for r in collisions if t0 <= t < t1]
    packet_rate = D / WINDOW_S
    collision_intensity = C / WINDOW_S
```

96 runs × 30 = **2880** lignes / taille, **même si** le RAW grossit : on résume des milliers d’événements en 30 vecteurs.

## Les 14 features (langage simple)

| Feature | Sens |
|---|---|
| packet_rate | RX réussies / 60 s |
| gw_success_rate | D / (D+C) |
| collision_rate | C / (D+C) |
| collision_intensity | C / 60 s |
| duplicate_rate | duplications GW / D |
| mean/min/max_duplicate_delay_s | délai 2e exemplaire − 1er |
| mean/std_rssi, mean/std_snir | radio des RX |
| interarrival_mean/std | écarts de temps entre RX |

Métadonnées (`run_id`, `scenario`, `Label`, …) **hors X**.

Exemple : fenêtre [360, 420) Replay, 12 RX, 2 collisions, 3 duplications → `packet_rate=0.2`, `collision_intensity=2/60`, `duplicate_rate=3/12`.

---

# PARTIE 7 — Labels V3

## CODE RÉEL

```python
def scheduled_label(scenario: str, t0: float, t1: float) -> str:
    if scenario == "Normal":
        return "Normal"
    if t1 <= 360 or t0 >= 1440:
        return "Normal"
    if t0 >= 360 and t1 <= 1440:
        return scenario
    raise ValueError(f"Fenetre mixte ...")
```

W=60 aligne les bords : pas de fenêtre à cheval.

Run Replay : [0,360) Normal, [360,1440) Replay, [1440,1800) Normal.

**Pourquoi pas tout le run = Replay ?** En V2 le one-shot + label scénario faisait apprendre « ce run a un replayer » au lieu de « l’attaque est active maintenant ».

Le Label RAW du logger (`labelFromActiveConfig`) **n’est pas** celui du dataset V3.

---

# PARTIE 8 — `train_eval_v3.py`

## X / Y

```python
X_train = df.loc[train_mask, FEATURES_X]
y_train = df.loc[train_mask, "Label"].to_numpy()
```

`CLASSES = ["Normal", "Jamming", "Replay", "Wormhole"]`.

## Split par run

```python
df["_group"] = df["n_nodes"].astype(str) + "::" + df["run_id"]
# stratify = scénario du run, pas le Label de fenêtre
train_test_split(..., stratify=runs["scenario"])
```

Sinon les fenêtres corrélées d’un même run iraient en train **et** en test.

## Preprocess

`SimpleImputer(median)` fit TRAIN ; `StandardScaler` pour ANN/LSTM fit TRAIN. RF/XGB : pas de scaler.

## A. RF

```python
rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
rf.fit(X_tr, y_train)
pred_rf = rf.predict(X_te)
```

## B. XGB

```python
xgb = XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, ...)
xgb.fit(X_tr, y_tr_i, sample_weight=sw)
pred_xgb = enc.inverse_transform(xgb.predict(X_te))
```

## C. ANN

`MLPClassifier(hidden_layer_sizes=(64, 32), activation="relu")` : 14 → 64 ReLU → 32 ReLU → 4 classes. Early stopping sur **des runs TRAIN** (pas le test).

## D. LSTM

`T=5` : 5 fenêtres = 5 minutes. Séquences **intra-run** uniquement (`make_sequences`). Y = Label de la **dernière** fenêtre. 32 unités, 25 epochs, batch 32, Adam 1e-3.

---

# PARTIE 9 — Boucle de scalabilité

```python
SIZES = [10, 20, 30, 50]
table_rows = []
for n in SIZES:
    df = load_csv(DATASETS[n])          # dataset_v3_{n}nodes.csv
    train_mask, test_mask, tr, te = split_by_run(df)
    bundle = eval_split(...)            # 4 modèles
    for model, res in bundle["results"].items():
        table_rows.append(row_metrics(model, n, res))
tab.to_csv(REPORTS / "scalability_table.csv")
plot_scalability(table_rows)
```

Chaque N a **son propre** train/test. On ne mélange pas 10 et 50 dans cette boucle (l’expérience 10+20→30+50 est **ensuite**, séparée).

Mêmes hyperparamètres : on compare l’effet de **N**, pas un retuning.

---

# PARTIE 10 — Accuracy vs Macro-F1

```python
acc = accuracy_score(y_true, y_pred)
f1 = f1_score(..., average="macro", labels=CLASSES)
```

Macro = moyenne **non pondérée** des F1 des 4 classes.

Par taille : 1584 Normal vs 432 Jamming / Replay / Wormhole.  
Un modèle qui dit toujours Normal a une Accuracy élevée et un **Macro-F1 faible**. D’où la métrique principale.

---

# PARTIE 11 — Courbe

```python
def plot_scalability(table_rows):
    nodes = SIZES   # [10, 20, 30, 50]  → axe X
    for metric, fname, ylabel in [
        ("accuracy", "accuracy_vs_nodes.png", "Accuracy"),
        ("macro_f1", "macro_f1_vs_nodes.png", "Macro-F1"),
    ]:
        for model in ["RF", "XGB", "ANN", "LSTM"]:
            ys = [row[metric] for row in table_rows if row["model"] == model]
            ax.plot(nodes, ys, marker="o", label=model)
        fig.savefig(REPORTS / fname, dpi=150)
```

Fichiers : `ml/v3/ml/reports/`.

Exemple RF Macro-F1 : 0.7688, 0.7661, 0.7730, 0.7281 → quatre points bleus.

---

# PARTIE 12 — Interprétation (résultats réels)

| Modèle | 10 | 20 | 30 | 50 | Lecture |
|---|---:|---:|---:|---:|---|
| LSTM | 0.834 | 0.798 | 0.796 | 0.797 | Le plus **stable** |
| RF | 0.769 | 0.766 | 0.773 | 0.728 | Casse à 50 |
| XGB | 0.759 | 0.746 | 0.758 | 0.716 | Casse à 50 |
| ANN | 0.760 | 0.772 | 0.749 | 0.708 | Plus sensible à 50 |

Collisions GW 3844 → 27142 : **corrélation** avec N (plus d’émetteurs, même canal). On **ne prouve pas** que « les collisions causent seules la baisse F1 » ; on constate densité + confusion Replay/Wormhole.

Scalabilité ici = **les détecteurs restent-ils utiles quand le réseau densifie ?** LSTM oui relativement ; arbres/ANN moins à 50.

---

# PARTIE 13 — 20 questions pièges

1. **Pourquoi plusieurs NED ?**  
   Oral : ne pas casser le 10.  
   Tech : modules nommés + positions.  
   Fichier : `AgriLoRaNetwork20.ned`.

2. **Pourquoi `numberOfNodes` ne suffit pas ?**  
   Oral : ça ne crée pas `loRaNode10`.  
   Fichier : comparer paramètre vs liste `loRaNodeK`.

3. **Pourquoi 2880 lignes partout ?**  
   Oral : 96×30 fenêtres de 60 s.  
   Fichier : `build_dataset_v3.py` `WINDOW_S`.

4. **Avez-vous copié le dataset 10 pour faire 50 ?**  
   Oral : non, RAW 111k → 216k.  
   Fichier : `v3_final_summary.json`.

5. **Pourquoi le RAW augmente ?**  
   Oral : plus d’émetteurs, plus de RX/collisions.  
   Fichier : `PacketEventLogger.cc`.

6. **Pourquoi Macro-F1 ?**  
   Oral : Normal 1584 vs 432.  
   Fichier : `metrics_bundle`.

7. **Pourquoi split par run ?**  
   Oral : pas de fuite intra-run.  
   Fichier : `split_by_run`.

8. **Pourquoi les mêmes hyperparamètres ?**  
   Oral : sinon on compare le tuning, pas N.  
   Fichier : `RF_PARAMS` hors de la boucle N.

9. **Pourquoi LSTM T=5 ?**  
   Oral : 5 min de contexte, Y = dernière fenêtre.  
   Fichier : `make_sequences`.

10. **Comment la courbe est générée ?**  
    `plot_scalability` + `SIZES`.

11. **Les nœuds sont câblés à la GW ?**  
    Non : radio `LoRaMedium`. `connections` = Ethernet GW–NS.

12. **50 nodes = 150 capteurs ?**  
    50 radios, 3 mesures **par paquet**.

13. **Smoke 20–100 s ?**  
    Pas la campagne. Configs `Smoke*`.

14. **Label RAW du logger = Label ML ?**  
    Non. ML = `scheduled_label`.

15. **Fenêtre mixte ?**  
    Interdite ; W aligne 360 et 1440.

16. **Même attaque à 50 ?**  
    `extends = Jamming, Nodes50`. Pas de retune.

17. **peerAppPath wormhole ?**  
    Nom du réseau change.

18. **Généralisation 10+20→30+50 ?**  
    Expérience **séparée** après la boucle N.

19. **Accuracy LSTM vs RF à 50 ?**  
    LSTM Macro-F1 tient ; Accuracy peut tromper.

20. **FLoRa modifié pour scaler ?**  
    Non.

---

# PARTIE 14 — Ordre de démo

| # | Fichier | Lignes à montrer | Phrase |
|---|---|---|---|
| 1 | `simulations/package.ned` | `loRaNode0`–`9` | « Réseau original 10 nœuds. » |
| 2 | `simulations/AgriLoRaNetwork20.ned` | `loRaNode10`–`19` | « On ajoute 10 nœuds, positions 0–9 inchangées. » |
| 3 | `simulations/AgriLoRaNetwork30.ned` | `loRaNode20`–`29` | « Densification 20→30. » |
| 4 | `simulations/AgriLoRaNetwork50.ned` | `loRaNode30`–`49` | « Jusqu’à 50 émetteurs. » |
| 5 | `simulations/omnetpp.ini` | `extends = Jamming, Nodes50` | « Mêmes attaques, autre réseau. » |
| 6 | `ml/v3/run_campaign_v3.py` | `all_jobs` | « 4×4×6×4 = 384. » |
| 7 | `ml/v3/build_dataset_v3.py` | `scheduled_label`, boucle W=60 | « 30 fenêtres, labels temporels. » |
| 8 | `ml/v3/features/dataset_v3_50nodes.csv` | en-tête 14 features + Label | « 2880 lignes, pas une copie du 10. » |
| 9 | `ml/v3/ml/train_eval_v3.py` | `for n in SIZES`, RF/XGB/ANN/LSTM | « Mêmes modèles, un split par N. » |
| 10 | `ml/v3/ml/reports/scalability_table.csv` | table | « Chiffres. » |
| 11 | `ml/v3/ml/reports/macro_f1_vs_nodes.png` | courbe | « LSTM stable, baisse arbres/ANN à 50. » |

Démo courbe sans ré-entraîner : `ml/v3/ml/plot_scalability_curves_v3.py`.

---

Fin du guide. Pour le nettoyage disque : attendre `GO CLEANUP`.
