def format_total(cents):
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return "%s$%d.%02d" % (sign, dollars, rest)


def line_label(raw):
    return raw.removeprefix("item:").strip()
