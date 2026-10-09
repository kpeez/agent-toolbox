def label(address):
    parts = [address.get(key, "").strip() for key in ("street", "city", "region")]
    return ", ".join(part for part in parts if part)
