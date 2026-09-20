#!/usr/bin/env python3
"""
Pipeline ML SÉPARÉ — Y = scénario du run (option B).
Ne remplace pas ml_common.py ni les rapports Y-émetteur.
"""
from pathlib import Path

import numpy as np
import pandas as pd
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
from sklearn.preprocessing import LabelEncoder, StandardScaler

HERE = Path(__file__).resolve().parent
ML_ROOT = HERE.parent

FEATURES = [
    "rssi_dBm",
    "snir_dB",
    "packet_size_B",
    "transmitted_bytes",
    "interarrival_s",
    "collision",
    "received",
    "energy_consumed",
]

CLASSES = ["Jamming", "Normal", "Replay", "Wormhole"]

if "sender_name" in FEATURES or "sender_mac" in FEATURES:
    raise RuntimeError("sender_name / sender_mac ne doivent jamais être dans FEATURES (X)")


def scenario_from_csv_label(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s in ("NoAttack", "NoAttack20", "Normal"):
        return "Normal"
    if "Jamming" in s:
        return "Jamming"
    if "Replay" in s:
        return "Replay"
    if "Wormhole" in s:
        return "Wormhole"
    return None


def load_df_scenario(csv_path):
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise SystemExit(f"Fichier introuvable : {csv_path}")
    df = pd.read_csv(csv_path)
    missing = [c for c in FEATURES + ["Label", "run_id"] if c not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes : {missing}")
    df = df.copy()
    df["scenario"] = df["Label"].map(scenario_from_csv_label)
    n0 = len(df)
    # Uniquement : scénario illisible ou run_id manquant.
    # On NE droppe PAS sender_mac / sender_name vides (collisions).
    df = df.dropna(subset=["scenario", "run_id"]).reset_index(drop=True)
    df["Label"] = df["scenario"]
    dropped = n0 - len(df)
    return df, dropped, n0


def split_par_run(df, test_size=0.25, seed=42):
    runs = df.groupby("run_id", as_index=False)["scenario"].first()
    train_runs, test_runs = train_test_split(
        runs["run_id"],
        test_size=test_size,
        random_state=seed,
        stratify=runs["scenario"],
    )
    train_mask = df["run_id"].isin(set(train_runs))
    test_mask = df["run_id"].isin(set(test_runs))
    return train_mask, test_mask


def tabular_xy(df, train_mask, test_mask):
    X = df[FEATURES]
    y = df["Label"]
    X_train, X_test = X.loc[train_mask], X.loc[test_mask]
    y_train, y_test = y.loc[train_mask], y.loc[test_mask]
    imputer = SimpleImputer(strategy="median")
    X_train_i = imputer.fit_transform(X_train)
    X_test_i = imputer.transform(X_test)
    return X_train_i, X_test_i, y_train, y_test, imputer


def make_windows_scenario(df, train_mask, seq_len=16, stride=8):
    """Y de CHAQUE fenêtre = scénario du run (pas le dernier paquet)."""
    imputer = SimpleImputer(strategy="median")
    imputer.fit(df.loc[train_mask, FEATURES])
    all_vals = imputer.transform(df[FEATURES])
    filled = df.copy()
    for i, col in enumerate(FEATURES):
        filled[col] = all_vals[:, i]

    scaler = StandardScaler()
    scaler.fit(filled.loc[train_mask, FEATURES])

    def windows_for(mask):
        Xs, ys, run_ids = [], [], []
        part = filled.loc[mask]
        for run_id, g in part.groupby("run_id", sort=False):
            g = g.sort_values("recv_time_s")
            arr = scaler.transform(g[FEATURES])
            scenario = g["scenario"].iloc[0]
            n = len(arr)
            if n == 0:
                continue
            if n < seq_len:
                pad = np.repeat(arr[:1], seq_len - n, axis=0)
                arr = np.vstack([pad, arr])
                n = seq_len
            starts = list(range(0, n - seq_len + 1, stride))
            if not starts:
                starts = [0]
            for s in starts:
                Xs.append(arr[s : s + seq_len])
                ys.append(scenario)
                run_ids.append(run_id)
        return np.asarray(Xs, dtype=np.float32), np.asarray(ys), np.asarray(run_ids)

    X_tr, y_tr, _ = windows_for(train_mask)
    X_te, y_te, _ = windows_for(~train_mask)
    enc = LabelEncoder()
    y_tr_i = enc.fit_transform(y_tr)
    y_te_i = enc.transform(y_te)
    return X_tr, y_tr_i, X_te, y_te_i, y_te, enc


def format_metrics(name, y_test, pred, extra_lines=None):
    acc = accuracy_score(y_test, pred)
    p = precision_score(y_test, pred, labels=CLASSES, average="macro", zero_division=0)
    r = recall_score(y_test, pred, labels=CLASSES, average="macro", zero_division=0)
    f1m = f1_score(y_test, pred, labels=CLASSES, average="macro", zero_division=0)
    report = classification_report(y_test, pred, labels=CLASSES, digits=3, zero_division=0)
    cm = confusion_matrix(y_test, pred, labels=CLASSES)
    cm_df = pd.DataFrame(cm, index=CLASSES, columns=CLASSES)
    support = {c: int((pd.Series(y_test) == c).sum()) for c in CLASSES}
    lines = [
        f"=== {name} AgriLoRaSec (Y = scénario du run) ===",
        f"Accuracy test : {acc:.3f}",
        f"Precision-macro test : {p:.3f}",
        f"Recall-macro test : {r:.3f}",
        f"F1-macro test : {f1m:.3f}",
        f"Support test : {support}",
        f"Classes présentes dans y_test : {sorted(pd.unique(y_test))}",
        "",
        "Rapport :",
        report,
        "Matrice de confusion (lignes = vrai, colonnes = prédit) :",
        cm_df.to_string(),
        "",
        f"Features X : {', '.join(FEATURES)}",
        "sender_name / sender_mac exclus de X.",
        "Y = scénario du run (pas l'émetteur du paquet).",
    ]
    if extra_lines:
        lines.extend([""] + extra_lines)
    text = "\n".join(lines)
    return {
        "acc": acc,
        "precision": p,
        "recall": r,
        "f1": f1m,
        "text": text,
        "support": support,
        "cm": cm_df,
    }
