def visible_records(query, records):
    if not query:
        return []
    needle = query.casefold()
    return [record for record in records if needle in record["title"].casefold()]
