#!/usr/bin/env python3
"""
Entraînement Y=scénario — n'écrase PAS les rapports Y-émetteur.
Usage:
  py -3 train_scenario.py --csv ..\\dataset.csv --out reports_10
  py -3 train_scenario.py --csv ..\\dataset_20nodes.csv --out reports_20
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ml_common_scenario import (
    FEATURES,
    CLASSES,
    load_df_scenario,
    split_par_run,
    tabular_xy,
    make_windows_scenario,
    format_metrics,
)


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


def eval_tabular(name, model, X_train, X_test, y_train, y_test, scale=False, encode=False, extra=None):
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
    return format_metrics(name, y_test, pred, extra)


def run_lstm(df, train_mask):
    X_tr, y_tr, X_te, y_te_i, y_te_names, enc = make_windows_scenario(
        df, train_mask, seq_len=SEQ_LEN
    )
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
    extra = [
        f"Fenêtres train {len(X_tr)} | test {len(X_te)} | longueur {SEQ_LEN} | stride 8",
        "Y de CHAQUE fenêtre = scénario du run (pas le dernier paquet).",
        f"Classes LSTM enc.classes_ = {list(enc.classes_)}",
        "PyTorch LSTM CPU, 25 époques, 32 unités.",
    ]
    m = format_metrics("LSTM", y_te_names, pred, extra)
    m["n_train_win"] = len(X_tr)
    m["n_test_win"] = len(X_te)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True, help="dossier de rapports (créé, jamais ml/*.txt existants)")
    args = ap.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = HERE / out
    out.mkdir(parents=True, exist_ok=True)

    df, dropped, n0 = load_df_scenario(args.csv)
    print("CSV", args.csv)
    print("lignes_brutes", n0, "drop_scenario_ou_run_id", dropped, "lignes_ML", len(df))
    print("Y", df["Label"].value_counts().sort_index().to_dict())
    print("runs", df.groupby("scenario")["run_id"].nunique().to_dict())
    print("FEATURES", FEATURES)
    assert "sender_name" not in FEATURES and "sender_mac" not in FEATURES

    train_mask, test_mask = split_par_run(df)
    extra_split = [
        f"Lignes ML {len(df)} (brutes {n0}, drop {dropped})",
        f"Lignes train {int(train_mask.sum())} | test {int(test_mask.sum())}",
        f"Runs train {df.loc[train_mask, 'run_id'].nunique()} | test {df.loc[test_mask, 'run_id'].nunique()}",
        f"Runs test par scénario : {df.loc[test_mask].groupby('scenario')['run_id'].nunique().to_dict()}",
    ]
    print("\n".join(extra_split))

    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)

    results = []
    m = eval_tabular(
        "Random Forest",
        RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        X_train, X_test, y_train, y_test, extra=extra_split,
    )
    (out / "rf.txt").write_text(m["text"], encoding="utf-8")
    print(m["text"])
    results.append(("Random Forest", m))

    m = eval_tabular(
        "XGBoost",
        XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            n_jobs=-1, eval_metric="mlogloss",
        ),
        X_train, X_test, y_train, y_test, encode=True, extra=extra_split,
    )
    (out / "xgb.txt").write_text(m["text"], encoding="utf-8")
    print(m["text"])
    results.append(("XGBoost", m))

    m = eval_tabular(
        "ANN (MLP)",
        MLPClassifier(
            hidden_layer_sizes=(64, 32), activation="relu", max_iter=400,
            random_state=42, early_stopping=True, validation_fraction=0.15,
        ),
        X_train, X_test, y_train, y_test, scale=True, encode=True, extra=extra_split,
    )
    (out / "ann.txt").write_text(m["text"], encoding="utf-8")
    print(m["text"])
    results.append(("ANN (MLP)", m))

    m = run_lstm(df, train_mask)
    m["text"] = m["text"] + "\n" + "\n".join(extra_split)
    (out / "lstm.txt").write_text(m["text"], encoding="utf-8")
    print(m["text"])
    results.append(("LSTM", m))

    lines = [
        "=== Y = scénario du run ===",
        f"CSV : {args.csv}",
        f"lignes ML={len(df)} train={int(train_mask.sum())} test={int(test_mask.sum())}",
        "",
        f"{'Modele':<22} {'Acc':>8} {'P-mac':>8} {'R-mac':>8} {'F1-mac':>8}  classes_y_test",
    ]
    for name, m in results:
        present = sorted(set(str(x) for x in (m.get('support') or {})))
        # from text
        lines.append(
            f"{name:<22} {m['acc']:8.3f} {m['precision']:8.3f} {m['recall']:8.3f} {m['f1']:8.3f}"
        )
    (out / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("Rapports :", out)


if __name__ == "__main__":
    main()
