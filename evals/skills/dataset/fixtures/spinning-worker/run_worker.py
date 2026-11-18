import json

from poller import wait_for_item


class FileQueue:
    def __init__(self, path):
        self.path = path

    def pop(self):
        with open(self.path) as handle:
            lines = handle.read().splitlines()
        if not lines:
            return None
        with open(self.path, "w") as handle:
            handle.write("\n".join(lines[1:]) + ("\n" if lines[1:] else ""))
        return json.loads(lines[0])


def main():
    queue = FileQueue("queue.jsonl")
    while True:
        item = wait_for_item(queue, 30)
        if item is not None:
            print("done", item, flush=True)


if __name__ == "__main__":
    main()
