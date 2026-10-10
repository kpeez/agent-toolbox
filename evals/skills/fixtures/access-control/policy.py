def can_read(viewer, document):
    return viewer["role"] in ("owner", "reader") and document["published"]
