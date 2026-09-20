#!/usr/bin/env python3
"""Chargement commun de dataset.csv — lecture seule, pas de leakage."""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "dataset.csv"

# Vérité terrain simulation (qui émet), PAS une feature X.
# Ancien dataset 10 nœuds (MAC figées) : jammer=0C, replayer=0D, wormhole B=0F.
ATTACK_MAC = {
    "0A-AA-00-00-00-0C": "Jamming",
    "0A-AA-00-00-00-0D": "Replay",
    "0A-AA-00-00-00-0F": "Wormhole",
}

ATTACK_NAME = {
    "jammer": "Jamming",
    "replayer": "Replay",
    "wormholeB": "Wormhole",
}

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

if "sender_name" in FEATURES or "sender_mac" in FEATURES:
    raise RuntimeError("sender_name / sender_mac ne doivent jamais être dans FEATURES (X)")


def _packet_y(mac):
    if pd.isna(mac) or str(mac).strip() == "":
        return None
    key = str(mac).strip().upper()
    return ATTACK_MAC.get(key, "Normal")


def _packet_y_from_name(name):
    if pd.isna(name) or str(name).strip() == "":
        return None
    n = str(name).strip()
    if n in ATTACK_NAME:
        return ATTACK_NAME[n]
    if n.startswith("loRaNode"):
        return "Normal"
    return None


def load_df():
    if not CSV_PATH.is_file():
        raise SystemExit(f"Fichier introuvable : {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    missing = [c for c in FEATURES + ["Label", "run_id", "sender_mac"] if c not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes : {missing}")
    df = df.copy()
    df["scenario"] = df["Label"]
    if "sender_name" in df.columns:
        df["Label"] = df["sender_name"].map(_packet_y_from_name)
    else:
        df["Label"] = df["sender_mac"].map(_packet_y)
    df = df.dropna(subset=["Label"]).reset_index(drop=True)
    return df


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


def format_report(name, y_test, pred, extra_lines=None):
    labels = sorted(pd.unique(y_test))
    acc = accuracy_score(y_test, pred)
    f1m = f1_score(y_test, pred, average="macro")
    report = classification_report(y_test, pred, labels=labels, digits=3, zero_division=0)
    cm = confusion_matrix(y_test, pred, labels=labels)
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    lines = [
        f"=== {name} AgriLoRaSec ===",
        f"CSV : {CSV_PATH}",
        f"Accuracy test : {acc:.3f}",
        f"F1-macro test : {f1m:.3f}",
        "",
        "Rapport :",
        report,
        "Matrice de confusion (lignes = vrai, colonnes = prédit) :",
        cm_df.to_string(),
        "",
        "Label = type d'émetteur (capteur=Normal, jammer, replay, wormhole).",
        "sender_name / sender_mac servent UNIQUEMENT à construire Y, jamais comme feature X.",
        f"Features X : {', '.join(FEATURES)}",
    ]
    if extra_lines:
        lines.extend([""] + extra_lines)
    text = "\n".join(lines)
    return text, acc, f1m


def write_report(filename, text):
    path = HERE / filename
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nRapport enregistré : {path}")
    return path


def make_windows(df, train_mask, seq_len=16, stride=8):
    """Séquences temporelles par run, pour LSTM. Y = Label du run."""
    imputer = SimpleImputer(strategy="median")
    train_vals = imputer.fit_transform(df.loc[train_mask, FEATURES])
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
            labs = g["Label"].to_numpy()
            n = len(arr)
            if n == 0:
                continue
            if n < seq_len:
                pad = np.repeat(arr[:1], seq_len - n, axis=0)
                arr = np.vstack([pad, arr])
                labs = np.concatenate([np.repeat(labs[:1], seq_len - n), labs])
                n = seq_len
            starts = list(range(0, n - seq_len + 1, stride))
            if not starts:
                starts = [0]
            for s in starts:
                Xs.append(arr[s : s + seq_len])
                ys.append(labs[s + seq_len - 1])
                run_ids.append(run_id)
        return np.asarray(Xs, dtype=np.float32), np.asarray(ys), np.asarray(run_ids)

    X_tr, y_tr, _ = windows_for(train_mask)
    X_te, y_te, _ = windows_for(~train_mask)
    enc = LabelEncoder()
    y_tr_i = enc.fit_transform(y_tr)
    y_te_i = enc.transform(y_te)
    return X_tr, y_tr_i, X_te, y_te_i, y_te, enc
