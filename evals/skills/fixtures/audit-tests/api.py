def _validate(data):
    missing = [key for key in ("origin", "destination") if not data.get(key)]
    return missing

def create(data):
    missing = _validate(data)
    if missing:
        raise ValueError("missing " + ",".join(missing))
    return (data["origin"], data["destination"])
