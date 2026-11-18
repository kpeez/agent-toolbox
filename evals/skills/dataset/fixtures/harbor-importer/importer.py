import csv
from io import StringIO

def read_rows(text):
    rows = list(csv.reader(StringIO(text)))
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:] if row]
