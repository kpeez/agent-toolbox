def summarize(cart):
    lines = cart["lines"]
    total = sum(line["price_cents"] * line["quantity"] for line in lines)
    count = sum(line["quantity"] for line in lines)
    return {"total_cents": total, "line_count": count}
