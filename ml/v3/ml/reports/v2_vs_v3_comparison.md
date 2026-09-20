# Comparaison V2 → V3 (lecture seule des résultats V2)

Aucun fichier V1/V2 n'a été modifié.

## Ce qui a changé expérimentalement

V2 labellisait **tout le run** selon le scénario. Replay et Wormhole étaient des
attaques **one-shot** (une capture / une réémission), donc la grande majorité des
fenêtres « Replay » ou « Wormhole » étaient en réalité du trafic Normal. Le modèle
apprenait un label de scénario prolongé, pas l'activité adversaire observée.

V3 restreint l'attaque à **[360 s, 1440 s)** et labellise **temporellement** :
Normal hors fenêtre, classe d'attaque pendant l'activité. Replay/Wormhole V3
sont multi-captures. Les classes restent déséquilibrées (1584 Normal vs 432 par
attaque). Macro-F1 est donc la métrique principale. Une baisse d'Accuracy n'est
pas à elle seule un échec si le Recall Replay/Wormhole devient informatif.

On ne conclut pas « V3 est meilleure » : on compare des **tâches différentes**.

## Macro-F1 V2 vs V3

| Model | N | Macro-F1 V2 | Macro-F1 V3 | Δ |
|---|---:|---:|---:|---:|
| RF | 10 | 0.4188 | 0.7688 | +0.3501 |
| RF | 20 | 0.4391 | 0.7661 | +0.3270 |
| RF | 30 | 0.4147 | 0.7730 | +0.3583 |
| RF | 50 | 0.4241 | 0.7281 | +0.3040 |
| XGB | 10 | 0.4342 | 0.7593 | +0.3251 |
| XGB | 20 | 0.4472 | 0.7457 | +0.2985 |
| XGB | 30 | 0.4417 | 0.7576 | +0.3159 |
| XGB | 50 | 0.4403 | 0.7160 | +0.2757 |
| ANN | 10 | 0.4265 | 0.7599 | +0.3334 |
| ANN | 20 | 0.4780 | 0.7718 | +0.2938 |
| ANN | 30 | 0.4148 | 0.7486 | +0.3338 |
| ANN | 50 | 0.4702 | 0.7081 | +0.2379 |
| LSTM | 10 | 0.4539 | 0.8336 | +0.3797 |
| LSTM | 20 | 0.4238 | 0.7982 | +0.3743 |
| LSTM | 30 | 0.4368 | 0.7956 | +0.3587 |
| LSTM | 50 | 0.3763 | 0.7972 | +0.4209 |

## Recall par classe V2 vs V3

### Recall Jamming

| Model | N | V2 | V3 | Δ |
|---|---:|---:|---:|---:|
| RF | 10 | 0.9944 | 1.0000 | +0.0056 |
| RF | 20 | 1.0000 | 1.0000 | +0.0000 |
| RF | 30 | 1.0000 | 1.0000 | +0.0000 |
| RF | 50 | 1.0000 | 1.0000 | +0.0000 |
| XGB | 10 | 0.9944 | 0.9815 | -0.0130 |
| XGB | 20 | 1.0000 | 1.0000 | +0.0000 |
| XGB | 30 | 1.0000 | 1.0000 | +0.0000 |
| XGB | 50 | 1.0000 | 1.0000 | +0.0000 |
| ANN | 10 | 0.9944 | 0.9815 | -0.0130 |
| ANN | 20 | 0.9889 | 1.0000 | +0.0111 |
| ANN | 30 | 1.0000 | 1.0000 | +0.0000 |
| ANN | 50 | 0.9889 | 0.9722 | -0.0167 |
| LSTM | 10 | 1.0000 | 1.0000 | +0.0000 |
| LSTM | 20 | 1.0000 | 1.0000 | +0.0000 |
| LSTM | 30 | 1.0000 | 1.0000 | +0.0000 |
| LSTM | 50 | 1.0000 | 1.0000 | +0.0000 |

### Recall Replay

| Model | N | V2 | V3 | Δ |
|---|---:|---:|---:|---:|
| RF | 10 | 0.1000 | 0.4444 | +0.3444 |
| RF | 20 | 0.3333 | 0.4630 | +0.1296 |
| RF | 30 | 0.2667 | 0.4815 | +0.2148 |
| RF | 50 | 0.2444 | 0.4167 | +0.1722 |
| XGB | 10 | 0.1111 | 0.4259 | +0.3148 |
| XGB | 20 | 0.3111 | 0.3981 | +0.0870 |
| XGB | 30 | 0.3167 | 0.4352 | +0.1185 |
| XGB | 50 | 0.2333 | 0.3796 | +0.1463 |
| ANN | 10 | 0.2611 | 0.5463 | +0.2852 |
| ANN | 20 | 0.2556 | 0.5000 | +0.2444 |
| ANN | 30 | 0.2167 | 0.5093 | +0.2926 |
| ANN | 50 | 0.1389 | 0.5093 | +0.3704 |
| LSTM | 10 | 0.0449 | 0.6111 | +0.5662 |
| LSTM | 20 | 0.1859 | 0.5093 | +0.3234 |
| LSTM | 30 | 0.2756 | 0.5556 | +0.2799 |
| LSTM | 50 | 0.1474 | 0.6759 | +0.5285 |

### Recall Wormhole

| Model | N | V2 | V3 | Δ |
|---|---:|---:|---:|---:|
| RF | 10 | 0.3389 | 0.6296 | +0.2907 |
| RF | 20 | 0.2500 | 0.6389 | +0.3889 |
| RF | 30 | 0.2167 | 0.6111 | +0.3944 |
| RF | 50 | 0.2167 | 0.4907 | +0.2741 |
| XGB | 10 | 0.3556 | 0.6296 | +0.2741 |
| XGB | 20 | 0.3500 | 0.6204 | +0.2704 |
| XGB | 30 | 0.2167 | 0.6019 | +0.3852 |
| XGB | 50 | 0.2500 | 0.4907 | +0.2407 |
| ANN | 10 | 0.0944 | 0.6111 | +0.5167 |
| ANN | 20 | 0.3333 | 0.6759 | +0.3426 |
| ANN | 30 | 0.3056 | 0.6204 | +0.3148 |
| ANN | 50 | 0.3611 | 0.5185 | +0.1574 |
| LSTM | 10 | 0.4423 | 0.8519 | +0.4095 |
| LSTM | 20 | 0.2692 | 0.8426 | +0.5734 |
| LSTM | 30 | 0.3269 | 0.6759 | +0.3490 |
| LSTM | 50 | 0.1218 | 0.5926 | +0.4708 |

## Lecture

Jamming était déjà facile en V2 (collisions). V3 ne doit pas « inventer » un gain
Jamming : vérifier que le Recall reste élevé sans retuning.

Replay/Wormhole V2 avaient un Recall bas et une confusion Normal/Replay/Wormhole
dominée par le one-shot + label prolongé. En V3, si `duplicate_rate` / delays
apparaissent dans l'importance RF/XGB, c'est **cohérent** avec des duplications GW
pendant 18 fenêtres, pas une preuve causale.

Si Replay et Wormhole restent confondues : les deux injectent un second exemplaire
d'une trame victime ; le GW ne voit pas le tunnel. Ce n'est pas un bug de labeling.

## Généralisation 10+20 → 30+50 (expérience séparée)

| Model | Acc V3 gen | Macro-F1 V3 gen |
|---|---:|---:|
| RF | 0.6542 | 0.5978 |
| XGB | 0.6087 | 0.5613 |
| ANN | 0.5766 | 0.5424 |
| LSTM | 0.6144 | 0.5784 |

V2 (référence, non modifié) :

| Model | Acc V2 gen | Macro-F1 V2 gen |
|---|---:|---:|
| RF | 0.4387 | 0.3986 |
| XGB | 0.4373 | 0.3963 |
| ANN | 0.4252 | 0.3643 |
| LSTM | 0.4425 | 0.3994 |
