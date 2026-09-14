"""The in-product local demo experience — lets a reviewer simulate realistic
sale scenarios and reset only that simulated data, entirely from the UI.
See app/services/demo_simulator.py for the actual simulation/reset logic;
this module is just the thin HTTP boundary plus the development-only gate.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.models.sale import Sale, SaleSource, TaxTreatment
from app.repositories.sale_repository import SaleRepository
from app.schemas.sale import SaleRead, sale_to_read
from app.schemas.validators import (
    validate_finite_decimal,
    validate_payment_method,
    validate_required_text,
    validate_transaction_currency,
)
from app.services.demo_simulator import DemoScenario, DemoSimulationError, reset_demo_data, simulate_sale

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str = Field(min_length=1, max_length=255)
    customer_contact: str | None = Field(default=None, max_length=255)
    service_name: str = Field(min_length=1, max_length=255)
    gross_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="ILS", min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=50)
    tax_treatment: TaxTreatment = Field(default=TaxTreatment.STANDARD)
    scenario: DemoScenario

    @field_validator("customer_name", "service_name")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return validate_required_text(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_transaction_currency(value)

    @field_validator("payment_method")
    @classmethod
    def _validate_payment_method(cls, value: str | None) -> str | None:
        return validate_payment_method(value)

    @field_validator("gross_amount")
    @classmethod
    def _validate_finite(cls, value: Decimal) -> Decimal:
        return validate_finite_decimal(value)  # type: ignore[return-value]


class DemoSimulationResponse(BaseModel):
    sale: SaleRead
    scenario: DemoScenario


class DemoResetPreviewResponse(BaseModel):
    demo_sales_count: int


class DemoResetResponse(BaseModel):
    deleted_sales_count: int
    deleted_events_count: int


def _require_development(settings: Settings) -> None:
    if settings.app_environment == "production":
        raise HTTPException(status_code=403, detail="The demo simulator is not available in production")


@router.get("/scenarios")
def list_demo_scenarios(settings: Settings = Depends(get_settings)) -> dict:
    _require_development(settings)
    return {"scenarios": [scenario.value for scenario in DemoScenario]}


@router.post("/simulate", response_model=DemoSimulationResponse, status_code=201)
def simulate_demo_sale(
    payload: DemoSimulationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DemoSimulationResponse:
    _require_development(settings)
    try:
        result = simulate_sale(
            db,
            customer_name=payload.customer_name,
            customer_contact=payload.customer_contact,
            service_name=payload.service_name,
            gross_amount=payload.gross_amount,
            currency=payload.currency,
            payment_method=payload.payment_method,
            tax_treatment=payload.tax_treatment,
            scenario=payload.scenario,
        )
    except DemoSimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repository = SaleRepository(db)
    sale = repository.get(result.sale_id)
    if sale is None:  # pragma: no cover - defensive, should be unreachable
        raise HTTPException(status_code=500, detail="Simulated sale could not be re-read")
    return DemoSimulationResponse(sale=sale_to_read(sale), scenario=result.scenario)


@router.get("/reset-preview", response_model=DemoResetPreviewResponse)
def preview_demo_reset(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> DemoResetPreviewResponse:
    """Lets the frontend show an honest confirmation dialog — "this will
    delete N demo sales" — before the reset itself is ever called."""
    _require_development(settings)
    count = db.scalar(select(func.count(Sale.id)).where(Sale.source == SaleSource.DEMO)) or 0
    return DemoResetPreviewResponse(demo_sales_count=count)


@router.post("/reset", response_model=DemoResetResponse)
def reset_demo_sales(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> DemoResetResponse:
    _require_development(settings)
    result = reset_demo_data(db)
    return DemoResetResponse(
        deleted_sales_count=result.deleted_sales_count, deleted_events_count=result.deleted_events_count
    )
