def deliver(preferences, transport, message):
    results = []
    for channel in preferences.get("channels", []):
        results.append(transport.send(channel, message))
    return results
