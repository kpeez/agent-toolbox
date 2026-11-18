def with_fee(cents, rate):
    fee = int(cents * rate)
    return cents + fee
