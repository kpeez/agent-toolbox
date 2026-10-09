def create_from_batch(data):
    missing = []
    if not data.get("origin"):
        missing.append("origin")
    if not data.get("destination"):
        missing.append("destination")
    if missing:
        raise ValueError("missing " + ",".join(missing))
    return {"origin": data["origin"], "destination": data["destination"]}
