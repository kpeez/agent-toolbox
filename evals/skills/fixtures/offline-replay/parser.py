def parse(line):
    fields = line.rstrip("\n").split("|")
    return {"id": fields[0], "kind": fields[1], "body": fields[2]}
