"""Data-access layer — keeps SQLAlchemy specifics out of the services layer."""
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc
import re
from sqlalchemy.exc import IntegrityError
from database.models import InvoiceORM, LineItemORM, VendorORM, CustomCategoryORM, UserORM
from models.invoice import Invoice
from models.vendor import Vendor
from datetime import date
from config.constants import CATEGORY_OPTIONS
from utils.categorizer import categorize_with_custom_categories


class DuplicateInvoiceError(Exception):
    """Raised only when a document is a strong duplicate of an existing row.

    Invoice number alone is intentionally insufficient: invoice numbering is
    vendor-scoped, can be reused, and may be absent.
    """

    def __init__(self, invoice_number: str | None, existing_id: int | None = None, reason: str | None = None):
        self.invoice_number = invoice_number
        self.existing_id = existing_id
        self.reason = reason or "matching vendor/document evidence"
        label = invoice_number or "(not specified)"
        super().__init__(
            f"Invoice '{label}' matches an existing invoice"
            + (f" (invoice ID {existing_id})" if existing_id is not None else "")
            + f": {self.reason}"
        )


class InvoiceLockedError(Exception):
    """Raised when trying to edit an invoice that has been locked.

    Locking an invoice on the History page means its data has been reviewed
    and confirmed correct — it must be unlocked again before it can be
    edited further.
    """

    def __init__(self, invoice_id: int):
        self.invoice_id = invoice_id
        super().__init__(f"Invoice {invoice_id} is locked and can't be edited — unlock it first.")


class UserRepository:
    """Data access for app login accounts (usernames are stored lowercase)."""

    def __init__(self, session: Session):
        self.session = session

    def count(self) -> int:
        return self.session.query(UserORM).count()

    def get_by_id(self, user_id: int) -> UserORM | None:
        return self.session.get(UserORM, user_id)

    def get_by_username(self, username: str) -> UserORM | None:
        return self.session.query(UserORM).filter(UserORM.username == (username or "").strip().lower()).first()

    def list_all(self) -> list[UserORM]:
        return self.session.query(UserORM).order_by(UserORM.username).all()

    def count_active_admins(self) -> int:
        return self.session.query(UserORM).filter(UserORM.role == "admin", UserORM.is_active.is_(True)).count()

    def create(self, username: str, password_hash: str, role: str = "user", must_change_password: bool = False) -> UserORM:
        user = UserORM(
            username=username.strip().lower(), password_hash=password_hash,
            role=role, is_active=True, must_change_password=must_change_password,
        )
        self.session.add(user)
        self.session.flush()
        return user


class InvoiceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_vendor(self, name: str, address: str | None = None, tax_id: str | None = None) -> VendorORM:
        name = (name or "Unknown Vendor").strip().upper()
        normalized = Vendor.normalize(name)
        vendor = (
            self.session.query(VendorORM)
            .filter(VendorORM.normalized_name == normalized)
            .first()
        )
        if vendor:
            return vendor
        vendor = VendorORM(name=name, normalized_name=normalized, address=address, tax_id=tax_id)
        self.session.add(vendor)
        self.session.flush()
        return vendor

    def get_by_invoice_number(self, invoice_number: str) -> InvoiceORM | None:
        """Return the first exact match for compatibility; numbers are no longer unique."""
        if not invoice_number:
            return None
        return (
            self.session.query(InvoiceORM)
            .filter(InvoiceORM.invoice_number == invoice_number)
            .order_by(InvoiceORM.id.asc())
            .first()
        )

    @staticmethod
    def _norm_number(value) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

    @staticmethod
    def _line_signature(items) -> tuple:
        rows = []
        for li in items or []:
            desc = getattr(li, "description", None)
            if desc is None and isinstance(li, dict):
                desc = li.get("description")
            desc = re.sub(r"[^A-Z0-9]+", " ", str(desc or "").upper()).strip()
            if not desc:
                continue
            def _v(name, default=0.0):
                value = getattr(li, name, None)
                if value is None and isinstance(li, dict):
                    value = li.get(name)
                try:
                    return round(float(value if value is not None else default), 2)
                except Exception:
                    return round(float(default), 2)
            rows.append((desc, _v("quantity", 1.0), _v("unit_price"), _v("amount")))
        return tuple(sorted(rows))

    def _find_duplicate(self, invoice, vendor_id: int | None, exclude_id: int | None = None):
        # Exact same source/page always wins, irrespective of later status edits.
        fingerprint = getattr(invoice, "source_fingerprint", None)
        if fingerprint:
            q = self.session.query(InvoiceORM).filter(InvoiceORM.source_fingerprint == fingerprint)
            if exclude_id is not None:
                q = q.filter(InvoiceORM.id != exclude_id)
            row = q.first()
            if row:
                return row, "same uploaded source/page fingerprint"

        q = self.session.query(InvoiceORM).options(selectinload(InvoiceORM.line_items))
        if vendor_id is not None:
            q = q.filter(InvoiceORM.vendor_id == vendor_id)
        else:
            q = q.filter(InvoiceORM.vendor_name == (getattr(invoice, "vendor_name", None) or ""))
        if exclude_id is not None:
            q = q.filter(InvoiceORM.id != exclude_id)

        new_num = self._norm_number(getattr(invoice, "invoice_number", None))
        new_date = getattr(invoice, "invoice_date", None)
        new_total = getattr(invoice, "total_amount", None)
        new_items = self._line_signature(getattr(invoice, "line_items", None))

        for row in q.all():
            row_num = self._norm_number(row.invoice_number)
            same_number = bool(new_num and row_num and new_num == row_num)
            if bool(new_num) != bool(row_num):
                same_number = False

            same_date = bool(new_date is not None and row.invoice_date is not None and new_date == row.invoice_date)
            same_total = False
            if new_total is not None and row.total_amount is not None:
                try:
                    same_total = abs(float(new_total) - float(row.total_amount)) <= 0.01
                except Exception:
                    pass
            row_items = self._line_signature(row.line_items)
            same_items = bool(new_items and row_items and new_items == row_items)

            # When both records contain item details, differing items are
            # strong evidence that a vendor reused the same invoice number for
            # a different transaction (QA explicitly exercises this case).
            # Therefore item equality is mandatory in that situation.
            if same_number:
                if new_items and row_items:
                    if same_items and (same_date or same_total):
                        return row, "same vendor + invoice number with matching line items and transaction details"
                elif same_date and same_total:
                    return row, "same vendor + invoice number with matching date and total"
            # Missing invoice numbers are allowed.  To avoid false positives,
            # require all three remaining strong signals when neither row has one.
            if not new_num and not row_num and same_date and same_total and same_items:
                return row, "same vendor/date/total/line items with no invoice number"

        return None, None

    def save(self, invoice: Invoice) -> InvoiceORM:
        invoice.vendor_name = (invoice.vendor_name or "Unknown Vendor").strip().upper()
        invoice.customer_name = (invoice.customer_name or "").strip().upper() or None
        invoice.invoice_number = str(invoice.invoice_number or "").strip() or None

        vendor = self.get_or_create_vendor(
            invoice.vendor_name, invoice.vendor_address, invoice.vendor_tax_id
        )
        existing, reason = self._find_duplicate(invoice, vendor.id)
        if existing:
            self.session.rollback()
            raise DuplicateInvoiceError(invoice.invoice_number, existing.id, reason)

        orm_invoice = InvoiceORM(
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date,
            date_uploaded=invoice.date_uploaded or date.today(),
            due_date=invoice.due_date,
            vendor_id=vendor.id,
            vendor_name=invoice.vendor_name,
            vendor_address=invoice.vendor_address,
            vendor_tax_id=invoice.vendor_tax_id,
            customer_name=invoice.customer_name,
            customer_contact=invoice.customer_contact,
            customer_address=invoice.customer_address,
            customer_tax_id=invoice.customer_tax_id,
            plate_number=invoice.plate_number,
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            tax_rate=invoice.tax_rate,
            discount=invoice.discount,
            withholding_tax=invoice.withholding_tax,
            zero_rated_sales=invoice.zero_rated_sales,
            vat_exempt_sales=invoice.vat_exempt_sales,
            total_amount=invoice.total_amount,
            current_charges_total=invoice.current_charges_total,
            previous_balance=invoice.previous_balance,
            currency=invoice.currency,
            payment_terms=invoice.payment_terms,
            category=invoice.category,
            source_file=invoice.source_file,
            source_fingerprint=invoice.source_fingerprint,
            enhanced_image_path=invoice.enhanced_image_path,
            original_filename=invoice.original_filename,
            ocr_engine_used=invoice.ocr_engine_used,
            confidence_score=invoice.confidence_score,
            status=invoice.status,
            raw_text=invoice.raw_text,
            vision_notes=invoice.vision_notes,
        )
        orm_invoice.line_items = [
            LineItemORM(
                description=li.description, quantity=li.quantity,
                unit_price=li.unit_price, amount=li.amount,
            )
            for li in invoice.line_items
        ]

        self.session.add(orm_invoice)
        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            raise RuntimeError(f"Database integrity error while saving invoice: {e}") from e
        self.session.refresh(orm_invoice)
        return orm_invoice

    def update(self, invoice_id: int, data: dict) -> InvoiceORM | None:
        """Apply manual corrections to an existing invoice's header fields.

        Used by the History page's "Edit" action to fix OCR misreads — e.g.
        invoices where labels/values are misaligned, or the scan is blurred.

        `data` may include any of: invoice_number, invoice_date, due_date,
        vendor_name, vendor_address, vendor_tax_id, customer_name,
        customer_contact, customer_address, customer_tax_id, plate_number, subtotal,
        tax_amount, tax_rate, discount, withholding_tax, zero_rated_sales, vat_exempt_sales,
        total_amount, currency, payment_terms, status, line_items (a
        full-replace list of {description, quantity, unit_price, amount}
        dicts — see below). Unrecognized keys are ignored.

        Raises DuplicateInvoiceError if the edit would rename invoice_number
        to one that already belongs to a *different* invoice.
        """
        obj = self.get_by_id(invoice_id)
        if not obj:
            return None

        if obj.locked:
            raise InvoiceLockedError(invoice_id)

        if "vendor_name" in data and data.get("vendor_name"):
            data["vendor_name"] = str(data["vendor_name"]).strip().upper()
            vendor = self.get_or_create_vendor(
                data["vendor_name"], data.get("vendor_address"), data.get("vendor_tax_id")
            )
            obj.vendor_id = vendor.id
            obj.vendor_name = data["vendor_name"]

        if "customer_name" in data:
            data["customer_name"] = str(data.get("customer_name") or "").strip().upper() or None
        if "invoice_number" in data:
            data["invoice_number"] = str(data.get("invoice_number") or "").strip() or None

        editable_fields = [
            "invoice_number", "invoice_date", "due_date", "customer_name",
            "customer_contact", "customer_address", "customer_tax_id", "plate_number",
            "vendor_address", "vendor_tax_id",
            "subtotal", "tax_amount", "tax_rate", "discount", "withholding_tax",
            "zero_rated_sales", "vat_exempt_sales", "total_amount",
            "current_charges_total", "previous_balance",
            "currency", "payment_terms", "status", "category", "source_file",
        ]
        for field in editable_fields:
            if field in data:
                setattr(obj, field, data[field])

        if "line_items" in data:
            # Full replace, not a merge — matches how the History page's
            # line-items editor works (it always submits the complete,
            # current set of rows). The relationship's cascade="all,
            # delete-orphan" (see database/models.py) means reassigning
            # this list is enough; SQLAlchemy deletes the rows that are no
            # longer referenced and inserts the new ones on commit.
            obj.line_items = [
                LineItemORM(
                    description=li.get("description") or "",
                    quantity=li.get("quantity") or 0.0,
                    unit_price=li.get("unit_price") or 0.0,
                    amount=li.get("amount") or 0.0,
                )
                for li in (data["line_items"] or [])
            ]

        # Re-check using the full logical duplicate policy after manual edits.
        existing, reason = self._find_duplicate(obj, obj.vendor_id, exclude_id=invoice_id)
        if existing:
            self.session.rollback()
            raise DuplicateInvoiceError(obj.invoice_number, existing.id, reason)

        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            raise RuntimeError(f"Database integrity error while updating invoice: {e}") from e

        self.session.refresh(obj)
        return obj

    def list_custom_categories(self) -> list[str]:
        return [r.name for r in self.session.query(CustomCategoryORM).order_by(CustomCategoryORM.name).all()]

    def add_custom_category(self, name: str) -> str:
        cleaned = " ".join((name or "").split()).strip()
        if not cleaned:
            raise ValueError("Category name cannot be blank.")
        if cleaned.casefold() in {c.casefold() for c in CATEGORY_OPTIONS}:
            raise ValueError("That is one of the built-in categories and already exists.")
        existing = self.session.query(CustomCategoryORM).all()
        if cleaned.casefold() in {c.name.casefold() for c in existing}:
            raise ValueError("That custom category already exists.")
        row = CustomCategoryORM(name=cleaned)
        self.session.add(row); self.session.commit(); self.session.refresh(row)
        return row.name

    def delete_custom_category(self, name: str) -> int:
        """Delete a user category and re-analyse invoices that used it.

        The eight built-in categories are immutable. Affected invoices are
        classified again using the normal built-in rules plus lightweight
        profiles learned from invoices in the *remaining* custom categories.
        This is an administrative category reassignment and therefore also
        applies to locked invoices without unlocking their reviewed data.
        """
        if name.casefold() in {c.casefold() for c in CATEGORY_OPTIONS}:
            raise ValueError("Built-in categories cannot be deleted.")
        row = self.session.query(CustomCategoryORM).filter(CustomCategoryORM.name == name).first()
        if not row:
            raise ValueError("Custom category not found.")

        remaining = [r.name for r in self.session.query(CustomCategoryORM).all() if r.name != name]
        profiles: dict[str, list[str]] = {c: [] for c in remaining}
        if remaining:
            examples = self.session.query(InvoiceORM).filter(InvoiceORM.category.in_(remaining)).all()
            for inv in examples:
                parts = [inv.vendor_name or ""] + [li.description or "" for li in inv.line_items]
                profiles[inv.category].append(" ".join(parts))

        affected = self.session.query(InvoiceORM).filter(InvoiceORM.category == name).all()
        for inv in affected:
            items = [{"description": li.description} for li in inv.line_items]
            inv.category = categorize_with_custom_categories(inv.vendor_name, items, profiles)

        self.session.delete(row)
        self.session.commit()
        return len(affected)

    def get_by_id(self, invoice_id: int) -> InvoiceORM | None:
        return self.session.query(InvoiceORM).filter(InvoiceORM.id == invoice_id).first()

    def set_locked(self, invoice_id: int, locked: bool) -> InvoiceORM | None:
        """Lock (or unlock) an invoice.

        A locked invoice is one whose extracted data has been reviewed and
        confirmed correct — `update()` refuses to edit it until it's
        unlocked again. Reports/export gating checks this flag too.
        """
        obj = self.get_by_id(invoice_id)
        if not obj:
            return None
        obj.locked = locked
        if locked:
            obj.status = "processed"
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def list_all(self, limit: int = 100, offset: int = 0, status: str | None = None) -> list[InvoiceORM]:
        # selectinload: ONE extra query for all line items instead of one lazy query per invoice (N+1).
        q = self.session.query(InvoiceORM).options(selectinload(InvoiceORM.line_items))
        if status:
            q = q.filter(InvoiceORM.status == status)
        return q.order_by(desc(InvoiceORM.created_at)).offset(offset).limit(limit).all()

    def search(self, keyword: str) -> list[InvoiceORM]:
        like = f"%{keyword}%"
        return (
            self.session.query(InvoiceORM)
            .options(selectinload(InvoiceORM.line_items))
            .filter(
                (InvoiceORM.invoice_number.ilike(like))
                | (InvoiceORM.vendor_name.ilike(like))
                | (InvoiceORM.customer_name.ilike(like))
            )
            .order_by(desc(InvoiceORM.created_at))
            .all()
        )

    def delete(self, invoice_id: int) -> bool:
        obj = self.get_by_id(invoice_id)
        if not obj:
            return False
        if obj.locked:
            raise InvoiceLockedError(invoice_id)
        self.session.delete(obj)
        self.session.commit()
        return True

    def stats(self) -> dict:
        from sqlalchemy import func
        total_invoices = self.session.query(func.count(InvoiceORM.id)).scalar() or 0
        total_amount = self.session.query(func.sum(InvoiceORM.total_amount)).scalar() or 0.0
        # Distinct vendors among invoices that currently exist — not a count
        # of the `vendors` table itself. That table is a permanent dimension
        # table (kept around for name-normalization/dedup lookups even after
        # an invoice is deleted), so counting its rows directly used to keep
        # "Vendors" inflated after the last invoice for a vendor was removed.
        # vendor_id is set on every invoice at creation (see
        # get_or_create_vendor above), and COUNT(DISTINCT ...) ignores NULLs
        # on its own, so this stays accurate without extra filtering.
        vendor_count = (
            self.session.query(func.count(func.distinct(InvoiceORM.vendor_id))).scalar() or 0
        )
        needs_review = (
            self.session.query(func.count(InvoiceORM.id))
            .filter(InvoiceORM.status == "needs_review")
            .scalar()
            or 0
        )
        return {
            "total_invoices": total_invoices,
            "total_amount": round(total_amount, 2),
            "vendor_count": vendor_count,
            "needs_review": needs_review,
        }
