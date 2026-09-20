#!/usr/bin/env python3
"""
LSTM sur des FENÊTRES temporelles par run (pas une ligne isolée).
Lit dataset.csv en lecture seule.
"""
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml_common import load_df, split_par_run, make_windows, format_report, write_report

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


def main():
    df = load_df()
    train_mask, _ = split_par_run(df)
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
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(X_te).to(device))
        pred_i = logits.argmax(1).cpu().numpy()
    pred = enc.inverse_transform(pred_i)

    extra = [
        f"Fenêtres train {len(X_tr)} | test {len(X_te)} | longueur {SEQ_LEN}",
        "Chaque fenêtre vient d'un seul run ; split toujours par run_id.",
        "Y de la fenêtre = Label du DERNIER paquet (détection d'émetteur).",
        "PyTorch LSTM CPU, 25 époques, 32 unités.",
    ]
    text, _, _ = format_report("LSTM", y_te_names, pred, extra)
    write_report("lstm_report.txt", text)


if __name__ == "__main__":
    main()
