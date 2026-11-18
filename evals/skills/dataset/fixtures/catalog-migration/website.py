from catalog import display_name


def render_product(product):
    dollars, cents = divmod(product["price_cents"], 100)
    return f"{display_name(product)} - ${dollars}.{cents:02d}"
