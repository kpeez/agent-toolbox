def create_from_api(data):
    missing = [key for key in ("origin", "destination") if not data.get(key)]
    if missing:
        raise ValueError("missing " + ",".join(missing))
    return {"origin": data["origin"], "destination": data["destination"]}
