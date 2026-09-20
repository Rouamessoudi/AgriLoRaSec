#!/usr/bin/env python3
"""XGBoost — lit dataset.csv, ne modifie pas la simulation."""
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from ml_common import load_df, split_par_run, tabular_xy, format_report, write_report


def main():
    df = load_df()
    train_mask, test_mask = split_par_run(df)
    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)

    enc = LabelEncoder()
    y_tr = enc.fit_transform(y_train)
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        eval_metric="mlogloss",
    )
    sw = compute_sample_weight("balanced", y_tr)
    model.fit(X_train, y_tr, sample_weight=sw)
    pred = enc.inverse_transform(model.predict(X_test))
    extra = [
        f"Runs train {df.loc[train_mask, 'run_id'].nunique()} | test {df.loc[test_mask, 'run_id'].nunique()}",
        f"Lignes train {train_mask.sum()} | test {test_mask.sum()}",
    ]
    text, _, _ = format_report("XGBoost", y_test, pred, extra)
    write_report("xgb_report.txt", text)


if __name__ == "__main__":
    main()
