import datetime

from due import due_date


def test_net_30_crosses_a_month():
    assert due_date(datetime.date(2026, 1, 15), 30) == datetime.date(2026, 2, 14)
