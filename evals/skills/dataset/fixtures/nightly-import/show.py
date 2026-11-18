import json
import sys

from pipeline import import_file


def main():
    for row in import_file(sys.argv[1]):
        print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
