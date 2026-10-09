def normalize(row):
    return {"id": str(row["id"]).strip(), "name": str(row.get("name", "")).strip()}
