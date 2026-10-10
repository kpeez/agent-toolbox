import json

def load_preferences(text):
    data = json.loads(text)
    zone = data.get("time_zone", "UTC").split("-")[0]
    return {"time_zone": zone, "digest": bool(data.get("digest", False))}

def save_preferences(value):
    return json.dumps({"time_zone": value["time_zone"], "digest": value["digest"]})
