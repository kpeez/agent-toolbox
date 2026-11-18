def wait_for_item(queue, clock, timeout, interval):
    started = clock()
    while clock() - started < timeout:
        item = queue.pop()
        if item is not None:
            return item
        clock.sleep(interval)
    return None
