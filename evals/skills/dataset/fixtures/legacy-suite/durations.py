def format_duration(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return str(hours) + "h " + str(minutes) + "m " + str(secs) + "s"
