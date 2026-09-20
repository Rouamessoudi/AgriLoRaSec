#!/usr/bin/env python3
"""ANN (MLP sklearn) — lit dataset.csv, ne modifie pas la simulation."""
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from ml_common import load_df, split_par_run, tabular_xy, format_report, write_report


def main():
    df = load_df()
    train_mask, test_mask = split_par_run(df)
    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_train)
    X_te = scaler.transform(X_test)

    model = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        max_iter=400,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.15,
    )
    enc = LabelEncoder()
    y_tr = enc.fit_transform(y_train)
    sw = compute_sample_weight("balanced", y_tr)
    model.fit(X_tr, y_tr, sample_weight=sw)
    pred = enc.inverse_transform(model.predict(X_te))
    extra = [
        f"Runs train {df.loc[train_mask, 'run_id'].nunique()} | test {df.loc[test_mask, 'run_id'].nunique()}",
        f"Époques (n_iter_) : {model.n_iter_}",
        "Normalisation StandardScaler fit sur le train seulement.",
    ]
    text, _, _ = format_report("ANN (MLP)", y_test, pred, extra)
    write_report("ann_report.txt", text)


if __name__ == "__main__":
    main()
