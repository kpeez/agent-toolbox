def validate(rows):
    if not all("id" in row for row in rows):
        raise ValueError("missing id")
    return rows
