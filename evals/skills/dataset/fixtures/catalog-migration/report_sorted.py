from catalog import display_name, load_products


def main():
    products = sorted(load_products(), key=lambda p: (display_name(p), p["id"]))
    for product in products:
        print(f"{display_name(product)} ({product['id']}): {product['price_cents']}")


if __name__ == "__main__":
    main()
