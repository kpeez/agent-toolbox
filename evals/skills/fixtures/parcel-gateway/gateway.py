def submit_charge(transport, account, amount, attempts=2):
    last_error = None
    for _ in range(attempts):
        try:
            request_id = transport.new_request_id()
            return transport.charge(request_id, account, amount)
        except TimeoutError as error:
            last_error = error
    raise last_error
