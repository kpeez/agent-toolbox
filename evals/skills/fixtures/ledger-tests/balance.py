def balance(entries):
    return sum(entry["cents"] for entry in entries)
