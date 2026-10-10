def cancel(invoice):
    if invoice["state"] == "paid":
        return False
    invoice["state"] = "cancelled"
    return True
