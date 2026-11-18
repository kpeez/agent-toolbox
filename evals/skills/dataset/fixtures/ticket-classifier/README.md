# Ticket classifier

A toy support-ticket classifier that labels each ticket `billing` or `outage`.
It is a logistic regression over word counts, trained with plain SGD in pure
Python. `data.py` generates the synthetic tickets from a fixed data seed: 1,500
for training and 600 held out for testing. `config.json` holds the training
settings: the learning rate (`lr`) and the number of epochs.

Train a model, then score it on the held-out tickets:

    python3 train.py --seed 1 --out model.json
    python3 eval.py --model model.json

`train.py` reads `config.json`. `--lr` overrides its learning rate, and
`--seed` sets the shuffle order of the training tickets. The model file records
the learning rate, epochs, seed, and data seed it was trained with. `eval.py`
prints the held-out accuracy, such as `accuracy=0.790 n=600`.
