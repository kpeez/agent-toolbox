import random

DATA_SEED = 7
LABELS = ("billing", "outage")
CUES = {
    "billing": ["invoice", "refund", "charge", "card", "payment", "receipt", "plan", "price"],
    "outage": ["down", "error", "timeout", "crash", "offline", "latency", "login", "blank"],
}
SHARED = ["please", "help", "today", "account", "still", "again", "since", "morning",
          "team", "app", "issue", "urgent", "my", "the", "is", "not"]
SPLIT_SIZES = {"train": 1500, "test": 600}


def make_ticket(rng):
    label = rng.choice(LABELS)
    other = LABELS[1 - LABELS.index(label)]
    words = []
    for _ in range(rng.randint(6, 12)):
        draw = rng.random()
        if draw < 0.30:
            words.append(rng.choice(CUES[label]))
        elif draw < 0.38:
            words.append(rng.choice(CUES[other]))
        else:
            words.append(rng.choice(SHARED))
    if rng.random() < 0.05:
        label = other
    return " ".join(words), label


def load_split(name):
    rng = random.Random(f"{DATA_SEED}-{name}")
    return [make_ticket(rng) for _ in range(SPLIT_SIZES[name])]
