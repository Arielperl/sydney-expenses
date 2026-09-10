from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sale import Sale


class SaleRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(self, sale: Sale) -> Sale:
        self._db.add(sale)
        self._db.commit()
        self._db.refresh(sale)
        return sale

    def get(self, sale_id: str) -> Sale | None:
        return self._db.get(Sale, sale_id)

    def list(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Sale]:
        stmt = select(Sale)
        if search:
            like_pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                Sale.customer_name.ilike(like_pattern) | Sale.service_name.ilike(like_pattern)
            )
        if status:
            stmt = stmt.where(Sale.status == status)
        if date_from:
            stmt = stmt.where(Sale.occurred_at >= date_from)
        if date_to:
            # date_to typically arrives as a date-only string parsed to
            # midnight (e.g. from a plain <input type="date">) — comparing
            # with `<=` against that midnight would silently exclude every
            # sale that happened later the same day. Treating it as the
            # start of the *next* day with `<` makes the whole day inclusive.
            end_of_day_exclusive = datetime.combine(date_to.date(), datetime.min.time()) + timedelta(days=1)
            stmt = stmt.where(Sale.occurred_at < end_of_day_exclusive)
        stmt = stmt.order_by(Sale.occurred_at.desc(), Sale.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def update(self, sale: Sale, updates: dict) -> Sale:
        for field, value in updates.items():
            setattr(sale, field, value)
        self._db.commit()
        self._db.refresh(sale)
        return sale

    def delete(self, sale: Sale) -> None:
        self._db.delete(sale)
        self._db.commit()
