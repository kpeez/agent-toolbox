# Vendor import

The nightly import currently reads CSV from a shared folder and writes one row at a time.
There are four vendors with slightly different headers. The new path should support local dry runs,
preserve the current row-level error report, and keep the operator's existing schedule.

A second session will implement the approved work. The team has not decided whether normalization
belongs in each vendor adapter or in one shared boundary. The current behavior is in importer.py.
