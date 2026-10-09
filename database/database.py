"""SQLAlchemy engine, session factory, and init helper."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings
from config.logging import get_logger

logger = get_logger("database")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    from database import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _ensure_new_columns()


def _ensure_new_columns():
    """Lightweight migration for columns added after a DB already exists.

    Base.metadata.create_all() only creates missing TABLES — it silently
    does nothing to a table that already exists, even if the ORM model now
    defines extra columns. Without this, an already-deployed sqlite DB
    (e.g. one carried over from before vision_notes was added) would throw
    "no such column" the first time it's queried. There's no Alembic in
    this project, so this is a deliberately minimal stand-in: add any
    columns that are missing, one ALTER TABLE at a time, and do nothing if
    they're already there.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return  # Non-sqlite deployments should use a real migration tool.

    new_columns = {
        "invoices": [
            ("vision_notes", "TEXT"), ("enhanced_image_path", "TEXT"),
            ("date_uploaded", "DATE"),
            ("vendor_address", "TEXT"), ("vendor_tax_id", "TEXT"),
            ("customer_contact", "TEXT"), ("customer_address", "TEXT"), ("customer_tax_id", "TEXT"),
            ("plate_number", "TEXT"),
            ("zero_rated_sales", "REAL"), ("vat_exempt_sales", "REAL"),
            ("current_charges_total", "REAL"), ("previous_balance", "REAL"),
            ("withholding_tax", "REAL"),
            # raw_text has been on the Invoice/InvoiceORM models since
            # before this migration list existed, so it was never added
            # here — but a sqlite file created before raw_text was on the
            # model (very early deployments) would still be missing the
            # column, and every subsequent save would silently insert NULL
            # into it instead of the actual OCR text. Listed here as a
            # safety net so a legacy DB gets the column added on next app
            # startup, same as the others above.
            ("raw_text", "TEXT"),
            ("payment_status", "TEXT NOT NULL DEFAULT 'unknown'"),
            ("source_fingerprint", "TEXT"),
        ],
    }
    with engine.connect() as conn:
        for table, columns in new_columns.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}
            for col_name, col_type in columns:
                if col_name not in existing:
                    logger.info(f"Migrating: adding column {table}.{col_name}")
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        # Backfill legacy rows once: their created_at timestamp is the historical upload/save time.
        if "date_uploaded" in {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoices)").fetchall()}:
            conn.exec_driver_sql("UPDATE invoices SET date_uploaded = DATE(created_at) WHERE date_uploaded IS NULL AND created_at IS NOT NULL")
        # v1.64 display normalization: vendor/customer names are stored in ALL CAPS.
        conn.exec_driver_sql("UPDATE invoices SET vendor_name = UPPER(TRIM(vendor_name)) WHERE vendor_name IS NOT NULL")
        conn.exec_driver_sql("UPDATE invoices SET customer_name = UPPER(TRIM(customer_name)) WHERE customer_name IS NOT NULL")
        conn.exec_driver_sql("UPDATE vendors SET name = UPPER(TRIM(name)) WHERE name IS NOT NULL")
        _repair_v167_zero_to_null_edit_bug(conn)
        conn.commit()

    _relax_invoice_number_constraint_if_needed()


def _relax_invoice_number_constraint_if_needed():
    """Migrate legacy SQLite DBs where invoice_number was NOT NULL + UNIQUE.

    Invoice numbers are vendor-scoped business references, not global record
    identifiers.  QA includes the same number from different vendors, and some
    legitimate/supplementary documents omit the number entirely.  SQLite cannot
    DROP a UNIQUE/NOT NULL constraint in-place, so rebuild only this table while
    preserving IDs and all columns.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        info = cur.execute("PRAGMA table_info(invoices)").fetchall()
        if not info:
            return
        inv_col = next((row for row in info if row[1] == "invoice_number"), None)
        unique_indexes = cur.execute("PRAGMA index_list(invoices)").fetchall()
        has_unique = any(bool(row[2]) for row in unique_indexes)
        needs_rebuild = bool(inv_col and inv_col[3]) or has_unique
        if not needs_rebuild:
            return

        logger.info("Migrating invoices table: invoice_number becomes nullable and non-unique")
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")
        try:
            # Keep this explicit so the migration is deterministic and does not
            # depend on SQLite's ALTER TABLE constraint limitations.
            cur.execute("""
                CREATE TABLE invoices_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    invoice_number VARCHAR, invoice_date DATE, date_uploaded DATE, due_date DATE,
                    vendor_id INTEGER REFERENCES vendors(id), vendor_name VARCHAR NOT NULL,
                    vendor_address VARCHAR, vendor_tax_id VARCHAR,
                    customer_name VARCHAR, customer_contact VARCHAR, customer_address VARCHAR, customer_tax_id VARCHAR,
                    plate_number VARCHAR, subtotal FLOAT, tax_amount FLOAT, tax_rate FLOAT, discount FLOAT,
                    withholding_tax FLOAT, zero_rated_sales FLOAT, vat_exempt_sales FLOAT, total_amount FLOAT,
                    current_charges_total FLOAT, previous_balance FLOAT, currency VARCHAR,
                    payment_terms VARCHAR, payment_status VARCHAR NOT NULL DEFAULT 'unknown', category VARCHAR NOT NULL DEFAULT 'Others',
                    source_file VARCHAR, source_fingerprint VARCHAR, enhanced_image_path VARCHAR, original_filename VARCHAR,
                    ocr_engine_used VARCHAR, confidence_score FLOAT, status VARCHAR, raw_text TEXT, vision_notes TEXT,
                    locked BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME
                )
            """)
            old_cols = {row[1] for row in info}
            target_cols = [
                "id", "invoice_number", "invoice_date", "date_uploaded", "due_date", "vendor_id", "vendor_name",
                "vendor_address", "vendor_tax_id", "customer_name", "customer_contact", "customer_address", "customer_tax_id",
                "plate_number", "subtotal", "tax_amount", "tax_rate", "discount", "withholding_tax", "zero_rated_sales",
                "vat_exempt_sales", "total_amount", "current_charges_total", "previous_balance", "currency", "payment_terms",
                "payment_status", "category", "source_file", "source_fingerprint", "enhanced_image_path", "original_filename",
                "ocr_engine_used", "confidence_score", "status", "raw_text", "vision_notes", "locked", "created_at",
            ]
            common = [c for c in target_cols if c in old_cols]
            cols = ", ".join(common)
            select_expr = {
                "vendor_name": "COALESCE(vendor_name, 'UNKNOWN VENDOR')",
                "category": "COALESCE(category, 'Others')",
                "payment_status": "COALESCE(payment_status, 'unknown')",
                "locked": "COALESCE(locked, 0)",
            }
            selected = ", ".join(select_expr.get(c, c) for c in common)
            cur.execute(f"INSERT INTO invoices_new ({cols}) SELECT {selected} FROM invoices")
            cur.execute("DROP TABLE invoices")
            cur.execute("ALTER TABLE invoices_new RENAME TO invoices")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_invoices_invoice_number ON invoices (invoice_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_invoices_payment_status ON invoices (payment_status)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_invoices_source_fingerprint ON invoices (source_fingerprint)")
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.execute("PRAGMA foreign_keys=ON")
    finally:
        raw.close()


def _repair_v167_zero_to_null_edit_bug(conn):
    """Restore explicit 0.00 amounts that v1.67 could accidentally save as NULL.

    The old History save payload used ``value or None`` for optional financial
    fields. Therefore an untouched, explicit 0.00 became NULL simply by
    clicking Save. Repair only invoices whose audit trail explicitly proves
    that exact transition, so genuine blank values are left untouched.
    """
    tables = {row[0] for row in conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "audit_logs" not in tables or "invoices" not in tables:
        return

    repairs = [
        ("Discount (internal): 0.00 → —", "discount"),
        ("Withholding Tax: 0.00 → —", "withholding_tax"),
        ("Zero-Rated Sales: 0.00 → —", "zero_rated_sales"),
        ("VAT-Exempt Sales: 0.00 → —", "vat_exempt_sales"),
    ]
    total_repaired = 0
    for marker, column in repairs:
        rows = conn.exec_driver_sql(
            "SELECT DISTINCT entity_id FROM audit_logs "
            "WHERE action = 'EDIT' AND entity_type = 'invoice' "
            "AND details LIKE ? AND entity_id IS NOT NULL",
            (f"%{marker}%",),
        ).fetchall()
        for (invoice_id,) in rows:
            result = conn.exec_driver_sql(
                f"UPDATE invoices SET {column} = 0.0 WHERE id = ? AND {column} IS NULL",
                (invoice_id,),
            )
            total_repaired += max(result.rowcount or 0, 0)
    if total_repaired:
        logger.info(f"Repaired {total_repaired} v1.67 explicit-zero financial value(s) saved as NULL")


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
