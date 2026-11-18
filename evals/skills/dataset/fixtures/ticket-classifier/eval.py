import argparse
import json

from data import load_split
from model import predict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="model.json")
    args = parser.parse_args()

    model = json.loads(open(args.model, encoding="utf-8").read())
    examples = load_split("test")
    correct = sum(predict(model, text) == label for text, label in examples)
    print(f"accuracy={correct / len(examples):.3f} n={len(examples)}")


if __name__ == "__main__":
    main()
