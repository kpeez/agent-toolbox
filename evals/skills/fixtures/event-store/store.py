def mark_delivery(event, response):
    if response.get("status") == "accepted":
        event["state"] = "sent"
    if response.get("status") != "accepted":
        event["state"] = "failed"
    return event
