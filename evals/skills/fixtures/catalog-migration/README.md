# Catalog data change

Products currently store a single `display_name` field in `products.json`, read through `catalog.py` (`load_products` and `display_name`). The requested change adds localized names while preserving the old field for existing callers (`website.py`, `export_csv.py`, `report_by_name.py`, and `report_sorted.py`, summarized in `callers.md`).

The migration design, compatibility period, and verification approach are still open. No implementation has been approved. The work is expected to span more than one session.

Commands:

    python3 export_csv.py --out products.csv
    python3 report_by_name.py
    python3 report_sorted.py
