import argparse
import csv

from catalog import display_name, load_products


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", default="products.json")
    parser.add_argument("--out", default="products.csv")
    args = parser.parse_args()

    products = load_products(args.products)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "display_name", "price_cents"])
        for product in products:
            writer.writerow([product["id"], display_name(product), product["price_cents"]])


if __name__ == "__main__":
    main()
