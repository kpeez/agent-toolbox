def relative_to(path, root):
    return path[len(root):]

def common_prefix(paths):
    prefix = paths[0]
    for path in paths[1:]:
        while not path.startswith(prefix):
            prefix = prefix[:-1]
    return prefix
