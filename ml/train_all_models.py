#!/usr/bin/env python3
"""Lance RF, XGBoost, ANN, LSTM sur le même split et écrit ml_comparison.txt."""
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from ml_common import (
    load_df,
    split_par_run,
    tabular_xy,
    format_report,
    write_report,
    HERE,
)
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
    text, acc, f1m = format_report(name, y_test, pred)
    return acc, f1m, text


def main():
    df = load_df()
    train_mask, test_mask = split_par_run(df)
    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)

    rows = []
    blocks = []

    acc, f1m, t = eval_tabular(
        "Random Forest",
        RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        X_train, X_test, y_train, y_test,
    )
    rows.append(("Random Forest", acc, f1m))
    blocks.append(t)
    (HERE / "rf_report.txt").write_text(t, encoding="utf-8")

    acc, f1m, t = eval_tabular(
        "XGBoost",
        XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            n_jobs=-1, eval_metric="mlogloss",
        ),
        X_train, X_test, y_train, y_test, encode=True,
    )
    rows.append(("XGBoost", acc, f1m))
    blocks.append(t)
    (HERE / "xgb_report.txt").write_text(t, encoding="utf-8")

    acc, f1m, t = eval_tabular(
        "ANN (MLP)",
        MLPClassifier(
            hidden_layer_sizes=(64, 32), activation="relu", max_iter=400,
            random_state=42, early_stopping=True, validation_fraction=0.15,
        ),
        X_train, X_test, y_train, y_test, scale=True, encode=True,
    )
    rows.append(("ANN (MLP)", acc, f1m))
    blocks.append(t)
    (HERE / "ann_report.txt").write_text(t, encoding="utf-8")

    # LSTM dans son propre module (fenêtres)
    from train_lstm import main as lstm_main
    lstm_main()
    lstm_txt = (HERE / "lstm_report.txt").read_text(encoding="utf-8")
    # extraire acc/f1 des lignes
    acc_l = f1_l = None
    for line in lstm_txt.splitlines():
        if line.startswith("Accuracy test"):
            acc_l = float(line.split(":")[1])
        if line.startswith("F1-macro test"):
            f1_l = float(line.split(":")[1])
    rows.append(("LSTM (fenêtres)", acc_l, f1_l))
    blocks.append(lstm_txt)

    table = ["=== Comparaison des 4 modèles (même dataset, split par run_id) ===", ""]
    table.append(f"{'Modèle':<22} {'Accuracy':>10} {'F1-macro':>10}")
    table.append("-" * 44)
    for name, a, f in rows:
        table.append(f"{name:<22} {a:10.3f} {f:10.3f}")
    table.append("")
    table.append("Y = paquet (capteur=Normal / jammer / replay / wormhole).")
    table.append("Les 3 premiers : une ligne = un événement. LSTM : fenêtre de 16.")
    table.append("sender_mac n'est PAS dans X (seulement pour construire Y).")
    table.append("")
    table.append("\n\n".join(blocks))
    out = "\n".join(table)
    write_report("ml_comparison.txt", out)


if __name__ == "__main__":
    main()
