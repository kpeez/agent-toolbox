from collections import Counter

from catalog import display_name, load_products


def main():
    counts = Counter(display_name(product) for product in load_products())
    for name in sorted(counts):
        print(f"{name}: {counts[name]}")


if __name__ == "__main__":
    main()
