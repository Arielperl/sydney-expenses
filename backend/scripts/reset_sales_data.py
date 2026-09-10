"""Deletes all sales/revenue data from the currently configured database,
leaving the schema, migration history, and every other setting untouched.

This is a destructive, deliberate developer action — not something the app
ever calls itself. It deletes every row in `sales` (which carries refund
state, document status/number/url, and provider references directly on each
row — there are no separate child tables for those) and every row in
`import_batches` (which only ever exists to group CSV-imported sales), all
inside one transaction so a failure partway through leaves nothing
half-deleted. No table is dropped, no migration is touched, and no other
table (there are none besides `alembic_version`) is read or written.

Run from backend/ with the venv active:

    python -m scripts.reset_sales_data
"""

from sqlalchemy import text

from app.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        sales_count = db.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
        batches_count = db.execute(text("SELECT COUNT(*) FROM import_batches")).scalar_one()

        db.execute(text("DELETE FROM sales"))
        db.execute(text("DELETE FROM import_batches"))
        db.commit()

        remaining_sales = db.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
        remaining_batches = db.execute(text("SELECT COUNT(*) FROM import_batches")).scalar_one()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"sales deleted: {sales_count}")
    print(f"import_batches deleted: {batches_count}")
    print(f"sales remaining: {remaining_sales}")
    print(f"import_batches remaining: {remaining_batches}")


if __name__ == "__main__":
    main()
