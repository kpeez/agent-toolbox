def resize(width, height, target):
    scale = min(target / width, target / height)
    return int(width * scale), int(height * scale)
