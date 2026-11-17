def format_total(cents):
<<<<<<< HEAD
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return "%s$%d.%02d" % (sign, dollars, rest)
=======
    dollars, rest = divmod(cents, 100)
    return "$%s.%02d" % (format(dollars, ","), rest)
>>>>>>> main
