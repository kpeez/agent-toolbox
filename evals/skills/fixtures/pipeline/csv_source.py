import csv
from io import StringIO
def read_csv(text):
    return list(csv.DictReader(StringIO(text)))
