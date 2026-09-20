#!/usr/bin/env python3
"""Evaluation ML V2 — fenêtres 60s. Ne touche pas aux datasets, attaques, FLoRa, ni build_dataset_v2.

LSTM : T=5 fenêtres (5 minutes). Justification :
- chaque run a 30 fenêtres de 60 s (simu 1800 s) ;
- T=5 = contexte court d'une attaque sans réutiliser l'ancien LSTM à 16 paquets ;
- sliding stride=1 à l'intérieur d'un run uniquement → 26 séquences / run ;
- Y = Label de la dernière fenêtre ; split run_id AVANT les séquences.
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

_VENV = _Path("/home/opp_env/AgriLoRaSec/ml/v2/ml/.venv/lib/python3.12/site-packages")
if _VENV.is_dir():
    sys.path.insert(0, str(_VENV))

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBClassifier

ROOT = Path("/home/opp_env/AgriLoRaSec")
FEAT = ROOT / "ml" / "v2" / "features"
OUT = ROOT / "ml" / "v2" / "ml"
MODELS = OUT / "models"
REPORTS = OUT / "reports"
CMS = OUT / "confusion_matrices"
BUILD_PY = ROOT / "ml" / "v2" / "build_dataset_v2.py"

FEATURES_X = [
    "packet_rate",
    "gw_success_rate",
    "collision_rate",
    "collision_intensity",
    "duplicate_rate",
    "mean_duplicate_delay_s",
    "min_duplicate_delay_s",
    "max_duplicate_delay_s",
    "mean_rssi",
    "std_rssi",
    "mean_snir",
    "std_snir",
    "interarrival_mean",
    "interarrival_std",
]

FORBIDDEN_IN_X = {
    "run_id",
    "scenario",
    "seed",
    "n_nodes",
    "SF",
    "window_start_s",
    "window_end_s",
    "activation_s",
    "Label",
    "sender_name",
    "sender_mac",
    "sequence_number",
    "packet_id",
    "packet_size_B",
    "transmitted_bytes",
    "energy_consumed",
    "tx_power_dBm",
    "coding_rate",
    "seq_seen_before",
    "diag_D",
    "diag_C",
    "diag_duplicate_count",
}

CLASSES = ["Normal", "Jamming", "Replay", "Wormhole"]
SIZES = [10, 20, 30, 50]
DATASETS = {n: FEAT / f"dataset_v2_{n}nodes.csv" for n in SIZES}
DATASETS["all"] = FEAT / "dataset_v2_all_nodes.csv"

SEED = 42
TEST_SIZE = 0.25
LSTM_T = 5
LSTM_STRIDE = 1
LSTM_EPOCHS = 25
LSTM_HIDDEN = 32
LSTM_BATCH = 32
LSTM_LR = 1e-3

RF_PARAMS = dict(n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1)
XGB_PARAMS = dict(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=SEED,
    n_jobs=-1,
    eval_metric="mlogloss",
)
ANN_PARAMS = dict(
    hidden_layer_sizes=(64, 32),
    activation="relu",
    max_iter=400,
    random_state=SEED,
    early_stopping=True,
    validation_fraction=0.15,
)


def leakage_check(feature_names):
    if list(feature_names) != FEATURES_X:
        raise SystemExit(f"LEAKAGE CHECK FAILED: X != 14 features validées: {feature_names}")
    leaked = [c for c in feature_names if c in FORBIDDEN_IN_X]
    if leaked:
        raise SystemExit(f"LEAKAGE CHECK FAILED: métadonnées dans X: {leaked}")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in FEATURES_X + ["Label", "run_id"] if c not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes dans {path}: {missing}")
    leakage_check(FEATURES_X)
    df = df.copy()
    df["_group"] = df["n_nodes"].astype(str) + "::" + df["run_id"].astype(str)
    return df


def split_by_run(df: pd.DataFrame, test_size=TEST_SIZE, seed=SEED):
    runs = df.groupby("_group", as_index=False)["Label"].first()
    train_runs, test_runs = train_test_split(
        runs["_group"],
        test_size=test_size,
        random_state=seed,
        stratify=runs["Label"],
    )
    train_set, test_set = set(train_runs), set(test_runs)
    inter = train_set & test_set
    if inter:
        raise SystemExit(f"SPLIT LEAKAGE: intersection run_id = {inter}")
    train_mask = df["_group"].isin(train_set)
    test_mask = df["_group"].isin(test_set)
    return train_mask, test_mask, train_set, test_set


def impute_train_only(X_train, X_test):
    imputer = SimpleImputer(strategy="median")
    X_tr = imputer.fit_transform(X_train)
    X_te = imputer.transform(X_test)
    return X_tr, X_te, imputer


def metrics_bundle(y_true, y_pred):
    acc = float(accuracy_score(y_true, y_pred))
    p = float(precision_score(y_true, y_pred, average="macro", zero_division=0, labels=CLASSES))
    r = float(recall_score(y_true, y_pred, average="macro", zero_division=0, labels=CLASSES))
    f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0, labels=CLASSES))
    report = classification_report(y_true, y_pred, labels=CLASSES, digits=4, zero_division=0)
    per_class = classification_report(
        y_true, y_pred, labels=CLASSES, digits=4, zero_division=0, output_dict=True
    )
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    return {
        "accuracy": acc,
        "macro_precision": p,
        "macro_recall": r,
        "macro_f1": f1,
        "report": report,
        "per_class": per_class,
        "cm": cm.tolist(),
    }


def save_cm(tag, cm):
    arr = np.array(cm)
    csv_path = CMS / f"cm_{tag}.csv"
    png_path = CMS / f"cm_{tag}.png"
    pd.DataFrame(arr, index=CLASSES, columns=CLASSES).to_csv(csv_path)
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.imshow(arr, cmap="Blues")
    ax.set_xticks(range(4), CLASSES, rotation=30, ha="right")
    ax.set_yticks(range(4), CLASSES)
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Vrai")
    ax.set_title(tag)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, str(arr[i, j]), ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(png_path, dpi=140)
    plt.close(fig)
    return str(csv_path), str(png_path)


def class_counts(y):
    c = Counter(y)
    return {k: int(c.get(k, 0)) for k in CLASSES}


class WindowLSTM(nn.Module):
    def __init__(self, n_feat, n_classes, hidden=LSTM_HIDDEN):
        super().__init__()
        self.lstm = nn.LSTM(n_feat, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, n_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def make_sequences(df, mask, imputer, scaler, enc, T=LSTM_T, stride=LSTM_STRIDE):
    part = df.loc[mask].copy()
    filled = imputer.transform(part[FEATURES_X])
    scaled = scaler.transform(filled)
    part = part.reset_index(drop=True)
    Xs, ys, groups = [], [], []
    tmp = part.copy()
    for i, col in enumerate(FEATURES_X):
        tmp[col] = scaled[:, i]
    for gid, g in tmp.groupby("_group", sort=False):
        g = g.sort_values("window_start_s")
        arr = g[FEATURES_X].to_numpy(dtype=np.float32)
        labs = g["Label"].to_numpy()
        n = len(arr)
        if n < T:
            continue
        for s in range(0, n - T + 1, stride):
            Xs.append(arr[s : s + T])
            ys.append(labs[s + T - 1])
            groups.append(gid)
    if not Xs:
        raise SystemExit("Aucune séquence LSTM construite")
    X = np.stack(Xs)
    y_names = np.asarray(ys)
    y_i = enc.transform(y_names)
    return X, y_i, y_names, np.asarray(groups)


def train_lstm(X_tr, y_tr, X_te, n_classes):
    device = torch.device("cpu")
    model = WindowLSTM(X_tr.shape[2], n_classes).to(device)
    counts = np.bincount(y_tr.astype(int), minlength=n_classes).astype(np.float32)
    counts = np.maximum(counts, 1.0)
    w = torch.tensor(counts.sum() / (len(counts) * counts), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.Adam(model.parameters(), lr=LSTM_LR)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr.astype(np.int64))),
        batch_size=LSTM_BATCH,
        shuffle=True,
    )
    model.train()
    for _ in range(LSTM_EPOCHS):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss_fn(model(xb), yb).backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(X_te).to(device)).argmax(1).cpu().numpy()
    return model, pred


def eval_split(tag, df, train_mask, test_mask, train_set, test_set, save_prefix):
    leakage_check(FEATURES_X)
    X_train = df.loc[train_mask, FEATURES_X]
    X_test = df.loc[test_mask, FEATURES_X]
    y_train = df.loc[train_mask, "Label"].to_numpy()
    y_test = df.loc[test_mask, "Label"].to_numpy()

    split_info = {
        "n_run_train": len(train_set),
        "n_run_test": len(test_set),
        "intersection": 0,
        "windows_train": int(train_mask.sum()),
        "windows_test": int(test_mask.sum()),
        "y_train": class_counts(y_train),
        "y_test": class_counts(y_test),
    }

    X_tr, X_te, imputer = impute_train_only(X_train, X_test)
    results = {}
    importances = {}

    rf = RandomForestClassifier(**RF_PARAMS)
    rf.fit(X_tr, y_train)
    pred_rf = rf.predict(X_te)
    results["RF"] = metrics_bundle(y_test, pred_rf)
    importances["RF"] = dict(zip(FEATURES_X, rf.feature_importances_.tolist()))
    save_cm(f"RF_{save_prefix}", results["RF"]["cm"])
    joblib.dump(rf, MODELS / f"rf_{save_prefix}.joblib")

    enc = LabelEncoder()
    enc.fit(CLASSES)
    y_tr_i = enc.transform(y_train)
    sw = compute_sample_weight("balanced", y_tr_i)
    xgb = XGBClassifier(**XGB_PARAMS)
    xgb.fit(X_tr, y_tr_i, sample_weight=sw)
    pred_xgb = enc.inverse_transform(xgb.predict(X_te))
    results["XGB"] = metrics_bundle(y_test, pred_xgb)
    importances["XGB"] = dict(zip(FEATURES_X, xgb.feature_importances_.tolist()))
    save_cm(f"XGB_{save_prefix}", results["XGB"]["cm"])
    joblib.dump(xgb, MODELS / f"xgb_{save_prefix}.joblib")

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)
    ann = MLPClassifier(**ANN_PARAMS)
    ann.fit(X_tr_s, y_tr_i, sample_weight=sw)
    pred_ann = enc.inverse_transform(ann.predict(X_te_s))
    results["ANN"] = metrics_bundle(y_test, pred_ann)
    save_cm(f"ANN_{save_prefix}", results["ANN"]["cm"])
    joblib.dump({"model": ann, "scaler": scaler, "imputer": imputer, "encoder": enc}, MODELS / f"ann_{save_prefix}.joblib")

    seq_scaler = StandardScaler()
    seq_scaler.fit(X_tr)
    Xseq_tr, yseq_tr, _, gtr = make_sequences(df, train_mask, imputer, seq_scaler, enc)
    Xseq_te, yseq_te, yseq_te_names, gte = make_sequences(df, test_mask, imputer, seq_scaler, enc)
    if set(gtr) & set(gte):
        raise SystemExit("LSTM sequence run_id intersection != 0")
    lstm, pred_i = train_lstm(Xseq_tr, yseq_tr, Xseq_te, len(CLASSES))
    pred_lstm = enc.inverse_transform(pred_i)
    results["LSTM"] = metrics_bundle(yseq_te_names, pred_lstm)
    results["LSTM"]["n_seq_train"] = int(len(Xseq_tr))
    results["LSTM"]["n_seq_test"] = int(len(Xseq_te))
    results["LSTM"]["T"] = LSTM_T
    save_cm(f"LSTM_{save_prefix}", results["LSTM"]["cm"])
    torch.save(lstm.state_dict(), MODELS / f"lstm_{save_prefix}.pt")

    joblib.dump(
        {"imputer": imputer, "label_encoder": enc, "seq_scaler": seq_scaler},
        MODELS / f"preproc_{save_prefix}.joblib",
    )

    return {
        "split": split_info,
        "results": results,
        "importances": importances,
        "ann_n_iter": int(getattr(ann, "n_iter_", -1)),
        "preprocessing": {
            "imputation": "SimpleImputer median, fit TRAIN only, transform TEST",
            "rf_xgb_scaling": "none (after median impute)",
            "ann_lstm_scaling": "StandardScaler fit TRAIN only",
            "label_encoder": "sklearn LabelEncoder fit on CLASSES order " + ",".join(CLASSES),
        },
    }


def write_text_report(path: Path, title: str, bundle: dict):
    lines = [title, ""]
    sp = bundle["split"]
    lines += [
        f"run_id train = {sp['n_run_train']}",
        f"run_id test  = {sp['n_run_test']}",
        f"intersection train/test = {sp['intersection']}",
        f"fenêtres train = {sp['windows_train']} | test = {sp['windows_test']}",
        f"Y train = {sp['y_train']}",
        f"Y test  = {sp['y_test']}",
        "",
        json.dumps(bundle["preprocessing"], ensure_ascii=False),
        "",
    ]
    for model, res in bundle["results"].items():
        lines += [
            f"=== {model} ===",
            f"Accuracy         = {res['accuracy']:.4f}",
            f"Macro Precision  = {res['macro_precision']:.4f}",
            f"Macro Recall     = {res['macro_recall']:.4f}",
            f"Macro F1         = {res['macro_f1']:.4f}",
            "",
            res["report"],
            "Confusion (rows=true, cols=pred, order Normal Jamming Replay Wormhole):",
            str(np.array(res["cm"])),
            "",
        ]
        if model in bundle.get("importances", {}):
            imp = sorted(bundle["importances"][model].items(), key=lambda kv: -kv[1])
            lines.append("Feature importance:")
            for k, v in imp:
                lines.append(f"  {k:24s} {v:.4f}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_scalability(table_rows):
    nodes = SIZES
    for metric, fname in [("accuracy", "accuracy_vs_nodes.png"), ("macro_f1", "macro_f1_vs_nodes.png")]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for model in ["RF", "XGB", "ANN", "LSTM"]:
            ys = [row[metric] for row in table_rows if row["model"] == model]
            ax.plot(nodes, ys, marker="o", label=model)
        ax.set_xlabel("Number of nodes")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_xticks(nodes)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(REPORTS / fname, dpi=150)
        plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    CMS.mkdir(parents=True, exist_ok=True)

    hashes_before = {str(p): md5(p) for p in list(DATASETS.values()) + [BUILD_PY]}
    (REPORTS / "dataset_hashes_before.json").write_text(json.dumps(hashes_before, indent=2), encoding="utf-8")

    table_rows = []
    all_bundles = {}
    for n in SIZES:
        df = load_csv(DATASETS[n])
        train_mask, test_mask, tr, te = split_by_run(df)
        bundle = eval_split(f"{n}nodes", df, train_mask, test_mask, tr, te, str(n))
        all_bundles[str(n)] = bundle
        write_text_report(REPORTS / f"report_{n}nodes.txt", f"ML V2 — {n} nodes", bundle)
        for model, res in bundle["results"].items():
            table_rows.append(
                {
                    "model": model,
                    "N": n,
                    "accuracy": res["accuracy"],
                    "macro_precision": res["macro_precision"],
                    "macro_recall": res["macro_recall"],
                    "macro_f1": res["macro_f1"],
                    "per_class": {
                        c: {
                            "precision": res["per_class"][c]["precision"],
                            "recall": res["per_class"][c]["recall"],
                            "f1": res["per_class"][c]["f1-score"],
                            "support": res["per_class"][c]["support"],
                        }
                        for c in CLASSES
                    },
                }
            )
        pd.DataFrame(bundle["importances"]["RF"], index=[0]).T.rename(columns={0: "importance"}).sort_values(
            "importance", ascending=False
        ).to_csv(REPORTS / f"importance_RF_{n}.csv")
        pd.DataFrame(bundle["importances"]["XGB"], index=[0]).T.rename(columns={0: "importance"}).sort_values(
            "importance", ascending=False
        ).to_csv(REPORTS / f"importance_XGB_{n}.csv")

    tab = pd.DataFrame(
        [
            {
                "Model": r["model"],
                "N": r["N"],
                "Accuracy": r["accuracy"],
                "Macro Precision": r["macro_precision"],
                "Macro Recall": r["macro_recall"],
                "Macro F1": r["macro_f1"],
            }
            for r in table_rows
        ]
    )
    tab.to_csv(REPORTS / "scalability_table.csv", index=False)
    plot_scalability(table_rows)

    # Généralisation 10+20 → 30+50
    df_tr = pd.concat([load_csv(DATASETS[10]), load_csv(DATASETS[20])], ignore_index=True)
    df_te = pd.concat([load_csv(DATASETS[30]), load_csv(DATASETS[50])], ignore_index=True)
    df_g = pd.concat([df_tr, df_te], ignore_index=True)
    train_mask = pd.Series([True] * len(df_tr) + [False] * len(df_te))
    test_mask = ~train_mask
    train_set = set(df_tr["_group"])
    test_set = set(df_te["_group"])
    if train_set & test_set:
        raise SystemExit("GEN split intersection != 0")
    gen = eval_split("gen_10_20_to_30_50", df_g, train_mask, test_mask, train_set, test_set, "gen")
    write_text_report(REPORTS / "report_generalization_10_20_to_30_50.txt", "GEN 10+20 → 30+50", gen)

    hashes_after = {str(p): md5(p) for p in list(DATASETS.values()) + [BUILD_PY]}
    unchanged = hashes_before == hashes_after
    (REPORTS / "dataset_hashes_after.json").write_text(json.dumps(hashes_after, indent=2), encoding="utf-8")

    summary = {
        "hashes_unchanged": unchanged,
        "hashes_before": hashes_before,
        "lstm_T": LSTM_T,
        "split": {"test_size": TEST_SIZE, "seed": SEED, "grouped_by": "_group = n_nodes::run_id"},
        "hyperparams": {
            "RF": RF_PARAMS,
            "XGB": {k: v for k, v in XGB_PARAMS.items()},
            "ANN": {k: v for k, v in ANN_PARAMS.items() if k != "hidden_layer_sizes"}
            | {"hidden_layer_sizes": [64, 32]},
            "LSTM": {"T": LSTM_T, "stride": LSTM_STRIDE, "hidden": LSTM_HIDDEN, "epochs": LSTM_EPOCHS, "batch": LSTM_BATCH, "lr": LSTM_LR},
        },
        "principal": table_rows,
        "generalization": {
            m: {k: gen["results"][m][k] for k in ["accuracy", "macro_precision", "macro_recall", "macro_f1"]}
            | {"per_class": {c: gen["results"][m]["per_class"][c] for c in CLASSES}}
            for m in gen["results"]
        },
        "splits": {k: v["split"] for k, v in all_bundles.items()},
        "importances": {k: v["importances"] for k, v in all_bundles.items()},
        "cms": {k: {m: v["results"][m]["cm"] for m in v["results"]} for k, v in all_bundles.items()},
        "gen_split": gen["split"],
        "gen_cms": {m: gen["results"][m]["cm"] for m in gen["results"]},
    }
    (REPORTS / "ml_v2_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print("HASHES_UNCHANGED", unchanged)
    print(tab.to_string(index=False))
    print("DONE")
    if not unchanged:
        sys.exit(2)


if __name__ == "__main__":
    main()
