#!/usr/bin/env python3
"""
Random Forest — détection paquet (Y = émetteur, pas le nom du run).
Lit dataset.csv sans le modifier.
"""
from sklearn.ensemble import RandomForestClassifier

from ml_common import FEATURES, load_df, split_par_run, tabular_xy, format_report, write_report
import pandas as pd


def main():
    df = load_df()
    train_mask, test_mask = split_par_run(df)
    X_train, X_test, y_train, y_test, _ = tabular_xy(df, train_mask, test_mask)

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    extra = [
        f"Runs train {df.loc[train_mask, 'run_id'].nunique()} | test {df.loc[test_mask, 'run_id'].nunique()}",
        f"Lignes train {int(train_mask.sum())} | test {int(test_mask.sum())}",
        "Importance des features :",
        imp.to_string(),
    ]
    text, _, _ = format_report("Random Forest", y_test, pred, extra)
    write_report("rf_report.txt", text)


if __name__ == "__main__":
    main()
