import csv


def write_csv(rows, stream):
    # BUG: header row is written after the data rows instead of before.
    writer = csv.writer(stream)
    for row in rows:
        writer.writerow(row)
    writer.writerow(["id", "name"])
