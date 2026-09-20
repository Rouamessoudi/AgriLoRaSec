#!/usr/bin/env python3
"""Entraîne RF/XGB/ANN/LSTM sur dataset_20nodes.csv.
Même code/hyperparamètres que train_all_models.py + train_lstm.py.
N'écrase pas dataset.csv ni les rapports 10 nœuds.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

import ml_common
from ml_common import FEATURES, load_df, split_par_run, tabular_xy, make_windows

ml_common.CSV_PATH = HERE / "dataset_20nodes.csv"
OUT = HERE / "reports_20nodes"
OUT.mkdir(exist_ok=True)


def metrics_block(name, y_test, pred):
    labels = sorted(pd.unique(y_test))
    acc = accuracy_score(y_test, pred)
    p = precision_score(y_test, pred, average="macro", zero_division=0)
    r = recall_score(y_test, pred, average="macro", zero_division=0)
    f1m = f1_score(y_test, pred, average="macro", zero_division=0)
    report = classification_report(y_test, pred, labels=labels, digits=3, zero_division=0)
    cm = confusion_matrix(y_test, pred, labels=labels)
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    text = "\n".join(
        [
            f"=== {name} AgriLoRaSec 20 nodes ===",
            f"CSV : {ml_common.CSV_PATH}",
            f"Lignes ML (après dropna Label) : {N_ROWS}",
            f"Accuracy test : {acc:.3f}",
            f"Precision-macro test : {p:.3f}",
            f"Recall-macro test : {r:.3f}",
            f"F1-macro test : {f1m:.3f}",
            "",
            "Rapport :",
            report,
            "Matrice de confusion (lignes = vrai, colonnes = prédit) :",
            cm_df.to_string(),
            "",
            f"Features X : {', '.join(FEATURES)}",
        ]
    )
    (OUT / f"{name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.txt").write_text(
        text, encoding="utf-8"
    )
    print(text)
    print()
    return acc, p, r, f1m, text


def eval_tabular(name, model, X_train, X_test, y_train, y_test, scale=False, encode=False):
    enc = None
    y_fit = y_train
    if encode:
        enc = LabelEncoder()
        y_fit = enc.fit_transform(y_train)
    Xs_tr, Xs_te = X_train, X_test
    if scale:
        sc = StandardScaler()
        Xs_tr = sc.fit_transform(X_train)
        Xs_te = sc.transform(X_test)
    sw = compute_sample_weight("balanced", y_fit)
    model.fit(Xs_tr, y_fit, sample_weight=sw)
    raw = model.predict(Xs_te)
    pred = enc.inverse_transform(raw) if enc is not None else raw
    return metrics_block(name, y_test, pred)


def run_lstm(df, train_mask):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    SEQ_LEN = 16
    EPOCHS = 25
    BATCH = 32
    LR = 1e-3

    class PacketLSTM(nn.Module):
        def __init__(self, n_feat, n_classes):
            super().__init__()
            self.lstm = nn.LSTM(n_feat, 32, batch_first=True)
            self.fc = nn.Linear(32, n_classes)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])

    X_tr, y_tr, X_te, y_te_i, y_te_names, enc = make_windows(df, train_mask, seq_len=SEQ_LEN)
    device = torch.device("cpu")
    model = PacketLSTM(X_tr.shape[2], len(enc.classes_)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    counts = np.bincount(y_tr.astype(int), minlength=len(enc.classes_)).astype(np.float32)
    counts = np.maximum(counts, 1.0)
    w = torch.tensor((counts.sum() / (len(counts) * counts)), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=w)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr.astype(np.int64))),
        batch_size=BATCH,
        shuffle=True,
    )
    model.train()
    for _ in range(EPOCHS):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss_fn(model(xb), yb).backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(X_te).to(device))
        pred_i = logits.argmax(1).cpu().numpy()
    pred = enc.inverse_transform(pred_i)
    acc, p, r, f1m, text = metrics_block("LSTM", y_te_names, pred)
    extra = f"\nFenêtres train {len(X_tr)} | test {len(X_te)} | longueur {SEQ_LEN}\n"
    (OUT / "lstm.txt").write_text(text + extra, encoding="utf-8")
    return acc, p, r, f1m, len(X_tr), len(X_te)


def main():
    global N_ROWS
    df = load_df()
    N_ROWS = len(df)
    print("N_ROWS_ML", N_ROWS)
    print("Y", df["Label"].value_counts().to_dict())
    print("FEATURES", FEATURES)
    train_mask, test_mask = split_par_run(df)
    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)
    print("train_rows", int(train_mask.sum()), "test_rows", int(test_mask.sum()))
    print("train_runs", df.loc[train_mask, "run_id"].nunique(), "test_runs", df.loc[test_mask, "run_id"].nunique())

    rows = []
    acc, p, r, f1m = eval_tabular(
        "Random Forest",
        RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        X_train, X_test, y_train, y_test,
    )[:4]
    rows.append(("Random Forest", acc, p, r, f1m))

    acc, p, r, f1m = eval_tabular(
        "XGBoost",
        XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            n_jobs=-1, eval_metric="mlogloss",
        ),
        X_train, X_test, y_train, y_test, encode=True,
    )[:4]
    rows.append(("XGBoost", acc, p, r, f1m))

    acc, p, r, f1m = eval_tabular(
        "ANN (MLP)",
        MLPClassifier(
            hidden_layer_sizes=(64, 32), activation="relu", max_iter=400,
            random_state=42, early_stopping=True, validation_fraction=0.15,
        ),
        X_train, X_test, y_train, y_test, scale=True, encode=True,
    )[:4]
    rows.append(("ANN (MLP)", acc, p, r, f1m))

    acc, p, r, f1m, ntr, nte = run_lstm(df, train_mask)
    rows.append(("LSTM", acc, p, r, f1m))

    lines = ["=== 20 nodes ===", f"lignes ML={N_ROWS}", ""]
    lines.append(f"{'Modele':<22} {'Acc':>8} {'P-mac':>8} {'R-mac':>8} {'F1-mac':>8}")
    for name, a, p, r, f in rows:
        lines.append(f"{name:<22} {a:8.3f} {p:8.3f} {r:8.3f} {f:8.3f}")
    summary = "\n".join(lines)
    (OUT / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
