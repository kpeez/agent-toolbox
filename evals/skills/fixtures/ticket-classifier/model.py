import math


def features(text):
    counts = {}
    for word in text.split():
        counts[word] = counts.get(word, 0) + 1
    return counts


def outage_probability(model, text):
    score = model["bias"] + sum(model["weights"].get(word, 0.0) * count
                                for word, count in features(text).items())
    return 1.0 / (1.0 + math.exp(-score))


def predict(model, text):
    return "outage" if outage_probability(model, text) >= 0.5 else "billing"
