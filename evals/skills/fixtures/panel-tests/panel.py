def render_row(label, value):
    return label + ": " + str(value)

def render_panel(rows):
    return "\n".join(render_row(label, value) for label, value in rows)
