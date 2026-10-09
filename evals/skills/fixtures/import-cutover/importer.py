def ingest(rows, writer):
    for row in rows:
        writer.write(row)
