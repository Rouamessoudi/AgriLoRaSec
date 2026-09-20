# AgriLoRaSec — sauvegarde et restauration (nouveau PC)

Ce document décrit comment **repartir de zéro** si le PC actuel disparaît.

Dépôt GitHub (privé) :

```text
https://github.com/Rouamessoudi/AgriLoRaSec.git
```

Branche : `main`

---

## CE QUI EST SAUVEGARDÉ SUR GITHUB

- Code source OMNeT (`src/` : attaques, `PacketEventLogger`, `PreserveHeaderLoRaMac`, `JammerSafe*`, `LoggingPacketForwarder`, etc.)
- Réseaux NED 10 / 20 / 30 / 50 nœuds
- `simulations/omnetpp.ini` et XML de configuration
- Makefile, README, backups légers du projet
- Scripts Python (`ml/`, `ml/v2/`, `ml/v3/`)
- Datasets fenêtrés V3 (`ml/v3/features/`)
- RAW CSV V3 (`ml/v3/raw/`)
- Modèles V3 (`ml/v3/ml/models/`)
- Rapports, matrices de confusion, `scalability_table.csv`
- `accuracy_vs_nodes.png`, `macro_f1_vs_nodes.png`
- `ml/v3/reports/GUIDE_SOUTENANCE_SCALABILITE.md`
- Historique Git, y compris l’ancien commit `8c01bf1`

## CE QUI DOIT ÊTRE RÉINSTALLÉ (pas dans Git)

- Windows + **WSL**
- **Git**
- **opp_env** / **OMNeT++ 6.3.0**
- **INET 4.5.4**
- **FLoRa 1.2.0**
- Environnement Python (`.venv` volontairement exclu)
- Binaire compilé `src/AgriLoRaSec` (on recompile)

## CE QUI DOIT ÊTRE RESTAURÉ DEPUIS UNE SAUVEGARDE EXTERNE

Ces éléments **ne sont pas** sur GitHub (trop gros ou reproductibles) :

| Élément | Emplacement actuel | Comment récupérer |
|---|---|---|
| Traces OMNeT `.sca` / `.vec` | `simulations/results/` (~2,3 Go) | Copier depuis `/home/opp_env/AgriLoRaSec_BACKUP_BEFORE_GIT/simulations/results/` (USB / disque) |
| Autres traces smoke/timing | `simulations/results_scale_smoke/`, `results_timingv2/` (fichiers `.sca`/`.vec` seulement) | Même backup local ; les CSV/log utiles sont déjà sur GitHub |
| `ml/v2/ml/.venv/` (~1,3 Go) | venv PyTorch / sklearn | **Ne pas copier** : recréer avec `pip` (voir plus bas) |

Copie de sécurité locale (ce PC) :

```text
/home/opp_env/AgriLoRaSec_BACKUP_BEFORE_GIT
```

**Ce dossier n’est pas sur GitHub.** Copiez-le sur un disque externe **avant** de changer de PC.

---

## 1. Installer Git (Windows)

```powershell
winget install Git.Git
git --version
```

Authentification GitHub (dépôt privé) :

```powershell
winget install GitHub.cli
gh auth login
```

---

## 2. Installer / configurer WSL

Dans PowerShell **administrateur** :

```powershell
wsl --install
```

Redémarrer si demandé. Vérifier :

```powershell
wsl -l -v
```

Le projet a été développé dans la distro **`opp_env`**. Sur un PC neuf, installez **opp_env** (environnement OMNeT++ isolé) plutôt que de recopier une distro corrompue.

Documentation opp_env : suivez le guide officiel d’installation d’`opp_env` pour Linux/WSL.

---

## 3. Installer opp_env, OMNeT++ 6.3.0, INET 4.5.4, FLoRa 1.2.0

Dans un shell WSL / opp_env (exemple ; adaptez si les commandes officielles évoluent) :

```bash
# OMNeT++ 6.3.0 via opp_env (noms de paquets typiques)
opp_env install omnetpp-6.3.0
opp_env install inet-4.5.4
opp_env install flora-1.2.0
```

Ouvrir un shell isolé :

```bash
opp_env shell --isolated
```

Vérifier que `opp_makemake` / `opp_run` existent.  
**INET, FLoRa et OMNeT++ ne sont pas dans le dépôt AgriLoRaSec.**

---

## 4. Récupérer le dépôt

```bash
cd ~
# ou : cd /home/opp_env
git clone https://github.com/Rouamessoudi/AgriLoRaSec.git
cd AgriLoRaSec
git lfs install   # inoffensif ; Git LFS n'est pas requis pour ce dépôt
git checkout main
git log --oneline -5
```

Vous devez voir au minimum :

- `merge: preserve existing GitHub history (8c01bf1)`
- `backup: complete AgriLoRaSec V3 scalability and ML results`
- `Initial commit: AgriLoRaSec PFE ...`

---

## 5. Git LFS

**Git LFS n’a pas été utilisé.** Un `git clone` classique suffit.  
Le plus gros fichier versionné est un modèle RF V2 (~77 Mo), sous la limite GitHub de 100 Mo.

---

## 6. Restaurer les gros fichiers non GitHub

Si vous avez copié `AgriLoRaSec_BACKUP_BEFORE_GIT` sur un disque `E:` (exemple) :

```bash
# Depuis WSL, après montage du disque
cp -a /mnt/e/AgriLoRaSec_BACKUP_BEFORE_GIT/simulations/results/. \
      ~/AgriLoRaSec/simulations/results/
```

Sans cette copie, les **datasets V3, modèles et PNG restent disponibles** (ils sont sur GitHub). Seules les traces scalaires/vectorielles OMNeT manqueront (reproductibles en relançant les sims, ce qui n’est **pas** nécessaire pour la soutenance ML).

---

## 7. Structure des dossiers attendue

```text
AgriLoRaSec/
  src/
  simulations/          # NED, omnetpp.ini, XML
  ml/v3/raw/
  ml/v3/features/
  ml/v3/ml/models/
  ml/v3/ml/reports/
  ml/v3/ml/confusion_matrices/
  Makefile
  README.md
  BACKUP_AND_RESTORE.md
```

Créer si besoin (vides, pour OMNeT) :

```bash
mkdir -p simulations/results
```

---

## 8. Recréer l’environnement Python

Le venv **n’est pas** sur GitHub. Dans `opp_env shell --isolated` :

```bash
cd ml/v2/ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy pandas scikit-learn xgboost matplotlib joblib torch --index-url https://download.pytorch.org/whl/cpu
pip install numpy pandas scikit-learn xgboost matplotlib joblib
```

(`train_eval_v3.py` utilise ce `.venv`.)  
Ajustez PyTorch CPU/GPU selon la machine. **Ne relancez pas** l’entraînement si les `.joblib` / `.pt` sont déjà présents.

---

## 9. Compiler AgriLoRaSec

Toujours dans `opp_env shell --isolated`, à la racine du projet :

```bash
make makefiles
make -j$(nproc)
```

Le binaire `src/AgriLoRaSec` (ou équivalent) doit apparaître.  
Les fichiers `/out/` et le binaire sont ignorés par Git : **c’est normal**.

---

## 10. Vérifier les datasets V3

```bash
ls -lh ml/v3/features/dataset_v3_{10,20,30,50,all_nodes}.csv
wc -l ml/v3/features/dataset_v3_*.csv
```

Attendu : fichiers présents (environ 2881 lignes par taille 10/20/30/50 = 1 en-tête + 2880 fenêtres).

RAW :

```bash
ls ml/v3/raw/10nodes | head
ls ml/v3/raw/20nodes | head
ls ml/v3/raw/30nodes | head
ls ml/v3/raw/50nodes | head
```

---

## 11. Vérifier les modèles

```bash
ls -lh ml/v3/ml/models/
```

Doivent exister : `rf_*.joblib`, `xgb_*.joblib`, `ann_*.joblib`, `lstm_*.pt`, `preproc_*.joblib` pour 10, 20, 30, 50 et `gen`.

---

## 12. Vérifier les rapports

```bash
cat ml/v3/ml/reports/scalability_table.csv
ls ml/v3/ml/confusion_matrices/
ls ml/v3/reports/
```

---

## 13. Ouvrir la courbe Macro-F1

Fichier exact :

```text
ml/v3/ml/reports/macro_f1_vs_nodes.png
```

Depuis Windows Explorer (WSL) :

```text
\\wsl$\opp_env\home\opp_env\AgriLoRaSec\ml\v3\ml\reports\macro_f1_vs_nodes.png
```

Ou, dans le shell :

```bash
# si un viewer est disponible
xdg-open ml/v3/ml/reports/macro_f1_vs_nodes.png
```

La courbe Accuracy :

```text
ml/v3/ml/reports/accuracy_vs_nodes.png
```

Pour **régénérer uniquement le PNG** (sans réentraîner) :

```bash
# dans opp_env shell --isolated, venv activé
python3 ml/v3/ml/plot_scalability_curves_v3.py
```

---

## 14. Vérifier que le projet recompile

```bash
opp_env shell --isolated
cd ~/AgriLoRaSec
make -j$(nproc)
ls -l src/AgriLoRaSec
```

Un lancement **court** (optionnel, pas une campagne) :

```bash
cd simulations
opp_run -u Cmdenv -c NoAttack --sim-time-limit=5s
```

Ne relancez **pas** les 384 runs ni `train_eval_v3.py` sauf besoin scientifique nouveau.

---

## Commandes de contrôle Git après clone

```bash
git remote -v
git status
git log --graph --oneline --decorate -10
git merge-base --is-ancestor 8c01bf1fbda835df4992b14f21a02eae57a2adec HEAD && echo "ancien commit GitHub conserve"
```

---

## Rappel

| Sur GitHub | À réinstaller | Sauvegarde externe |
|---|---|---|
| Code, NED, INI, ML V3 (raw + features + modèles + rapports + PNG) | Git, WSL, opp_env, OMNeT++ 6.3.0, INET 4.5.4, FLoRa 1.2.0, venv Python | `simulations/results/` (.sca/.vec) + copie `AgriLoRaSec_BACKUP_BEFORE_GIT` |
