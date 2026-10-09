def apply(state, event):
    state[event["id"]] = event["body"]
    return state
