from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.sale import SaleRead


class TopService(BaseModel):
    service_name: str
    total: Decimal
    count: int


class RevenueTrendPoint(BaseModel):
    period_start: date_type
    total: Decimal


class DashboardStats(BaseModel):
    net_revenue_this_month: Decimal
    net_revenue_previous_month: Decimal
    percentage_change: float | None
    successful_sales_count: int
    average_transaction_value: Decimal | None
    gross_revenue: Decimal
    vat_collected: Decimal
    processing_fees: Decimal
    recent_sales: list[SaleRead]
    top_services: list[TopService]
    revenue_trend: list[RevenueTrendPoint]
    pending_documents_count: int
    pending_documents_total: Decimal
    document_failures_count: int
    failed_payments_count: int
    refunds_count: int
    refunds_total: Decimal
