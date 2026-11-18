import argparse
import json
import random

from data import DATA_SEED, load_split
from model import features, outage_probability


def train(examples, lr, epochs, seed):
    rng = random.Random(seed)
    model = {"weights": {}, "bias": 0.0}
    order = list(range(len(examples)))
    for _ in range(epochs):
        rng.shuffle(order)
        for index in order:
            text, label = examples[index]
            gradient = outage_probability(model, text) - (label == "outage")
            model["bias"] -= lr * gradient
            for word, count in features(text).items():
                model["weights"][word] = model["weights"].get(word, 0.0) - lr * gradient * count
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--lr", type=float, help="overrides lr in the config")
    parser.add_argument("--seed", type=int, default=1, help="seeds the shuffle order")
    parser.add_argument("--out", default="model.json")
    args = parser.parse_args()

    config = json.loads(open(args.config, encoding="utf-8").read())
    lr = config["lr"] if args.lr is None else args.lr
    model = train(load_split("train"), lr, config["epochs"], args.seed)
    model["run"] = {"lr": lr, "epochs": config["epochs"], "seed": args.seed, "data_seed": DATA_SEED}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(model, handle, indent=2, sort_keys=True)
    print(f"trained lr={lr} epochs={config['epochs']} seed={args.seed} -> {args.out}")


if __name__ == "__main__":
    main()
