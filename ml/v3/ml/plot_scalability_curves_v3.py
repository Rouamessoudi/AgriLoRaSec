#!/usr/bin/env python3
"""Demo encadrant : courbes de scalabilité V3 (Accuracy et Macro-F1).

Lit UNIQUEMENT les scores déjà calculés :
    ml/v3/ml/reports/scalability_table.csv

Ne relance ni simulation OMNeT++, ni entraînement RF/XGB/ANN/LSTM.

Le tracé est le même que plot_scalability() dans train_eval_v3.py
(lignes 545-563).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPORTS = Path("/home/opp_env/AgriLoRaSec/ml/v3/ml/reports")
CSV = REPORTS / "scalability_table.csv"
NODES = [10, 20, 30, 50]
MODELS = ["RF", "XGB", "ANN", "LSTM"]


def plot_scalability_from_csv():
    tab = pd.read_csv(CSV)
    print(tab.to_string(index=False))
    print()

    for col, fname, ylabel in [
        ("Accuracy", "accuracy_vs_nodes.png", "Accuracy"),
        ("Macro F1", "macro_f1_vs_nodes.png", "Macro-F1"),
    ]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for model in MODELS:
            ys = tab.loc[tab["Model"] == model].set_index("N").loc[NODES, col].tolist()
            ax.plot(NODES, ys, marker="o", label=model)
        ax.set_xlabel("Number of nodes")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} vs number of nodes (V3, W=60 s)")
        ax.set_xticks(NODES)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        out = REPORTS / fname
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print("écrit", out)


if __name__ == "__main__":
    plot_scalability_from_csv()
