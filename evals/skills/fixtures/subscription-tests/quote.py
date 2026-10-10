def monthly_total(cents, months):
    if months <= 0:
        raise ValueError("months must be positive")
    return cents * months
