import argparse
import csv
import sys

HEADER = ["number", "customer", "total"]


def write_rows(invoices, out):
    writer = csv.writer(out, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(HEADER)
    for invoice in invoices:
        writer.writerow([invoice["number"], invoice["customer"], "%.2f" % (invoice["cents"] / 100)])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export invoices as CSV.")
    parser.add_argument("--out", help="file to write; standard output when absent")
    args = parser.parse_args(argv)
    invoices = [{"number": "INV-1", "customer": "Acme, Ltd", "cents": 1205}]
    if args.out:
        with open(args.out, "w", newline="") as out:
            write_rows(invoices, out)
    else:
        write_rows(invoices, sys.stdout)


if __name__ == "__main__":
    main()
