import time


def wait_for_item(queue, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = queue.pop()
        if item is not None:
            return item
    return None
