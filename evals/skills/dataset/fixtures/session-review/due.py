import datetime


def due_date(issued, terms_days):
    return issued + datetime.timedelta(days=terms_days)
