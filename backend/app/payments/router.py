"""Future payments API routes.

##############################################################################
#  INTENTIONALLY INACTIVE — DO NOT REGISTER THIS ROUTER.                     #
#                                                                            #
#  It is not included in app.api.router or app.main, and a test asserts     #
#  that no /api/payments route exists on the production app. Activating it  #
#  requires the checklist in docs/payments-foundation.md ("Before any real  #
#  payment"), starting with a real, officially documented provider adapter. #
##############################################################################

When activated, these routes run behind ``protect_workspace`` in app.main,
which already: authenticates the user, rejects support accounts on business
routes, blocks viewers from non-GET requests, checks the Origin header on
mutations, and sets ``Cache-Control: no-store``. The limiter below adds a
per-user budget on money-moving operations.

Provider webhooks are deliberately not exposed here: a public webhook route
must resolve the business from an unguessable per-connection token (as the
Grow/Cardcom connections do today) and be exempted from cookie auth in
``protect_workspace`` — design work for the first real provider.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.database import get_db
from app.payments import errors
from app.payments.permissions import actor_from_request_user
from app.payments.providers.registry import build_default_registry
from app.payments.schemas import (
    CreatePaymentIntentRequest,
    CreateRefundRequest,
    PaymentIntentResponse,
    PaymentRefundResponse,
)
from app.payments.service import CreatePaymentIntentInput, PaymentService

router = APIRouter(prefix="/payments", tags=["payments (inactive)"])

_money_moves_by_user = RateLimiter(max_requests=30, window_seconds=60)

_ERROR_STATUS = {
    errors.PaymentPermissionError: 403,
    errors.PaymentNotFoundError: 404,
    errors.PaymentValidationError: 422,
    errors.IdempotencyConflictError: 409,
    errors.DuplicateExternalReferenceError: 409,
    errors.ConcurrentUpdateError: 409,
    errors.PaymentStateError: 409,
    errors.InvalidTransitionError: 409,
    errors.RefundLimitExceededError: 422,
    errors.UntrustedCheckoutUrlError: 502,
    errors.ProviderError: 502,
}


def _service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db, build_default_registry(get_settings().app_environment))


def _actor(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "Authentication required")
    return actor_from_request_user(user)


def _call(operation):
    try:
        return operation()
    except tuple(_ERROR_STATUS) as error:
        status = next(code for kind, code in _ERROR_STATUS.items() if isinstance(error, kind))
        detail = "The payment provider is unavailable" if status == 502 else str(error)
        raise HTTPException(status, detail) from None


@router.post("/intents", response_model=PaymentIntentResponse, status_code=201)
def create_intent(body: CreatePaymentIntentRequest, request: Request,
                  idempotency_key: str = Header(..., alias="Idempotency-Key"),
                  service: PaymentService = Depends(_service)):
    actor = _actor(request)
    _money_moves_by_user.check(f"{actor.business_id}:{actor.user_id}")
    return _call(lambda: service.create_payment_intent(actor, CreatePaymentIntentInput(
        idempotency_key=idempotency_key, **body.model_dump())))


@router.post("/intents/{intent_id}/checkout", response_model=PaymentIntentResponse)
def request_checkout(intent_id: str, request: Request, service: PaymentService = Depends(_service)):
    actor = _actor(request)
    _money_moves_by_user.check(f"{actor.business_id}:{actor.user_id}")
    return _call(lambda: service.request_checkout(actor, intent_id))


@router.post("/intents/{intent_id}/cancel", response_model=PaymentIntentResponse)
def cancel_intent(intent_id: str, request: Request, service: PaymentService = Depends(_service)):
    return _call(lambda: service.cancel_payment(_actor(request), intent_id))


@router.post("/intents/{intent_id}/refunds", response_model=PaymentRefundResponse, status_code=201)
def create_refund(intent_id: str, body: CreateRefundRequest, request: Request,
                  idempotency_key: str = Header(..., alias="Idempotency-Key"),
                  service: PaymentService = Depends(_service)):
    actor = _actor(request)
    _money_moves_by_user.check(f"{actor.business_id}:{actor.user_id}")
    return _call(lambda: service.create_refund(
        actor, intent_id, idempotency_key=idempotency_key, amount_minor=body.amount_minor, reason=body.reason))


@router.get("/intents/{intent_id}", response_model=PaymentIntentResponse)
def get_intent(intent_id: str, request: Request, service: PaymentService = Depends(_service)):
    return _call(lambda: service.get_payment(_actor(request), intent_id))


@router.get("/intents", response_model=list[PaymentIntentResponse])
def list_intents(request: Request, limit: int = 50, offset: int = 0, service: PaymentService = Depends(_service)):
    return _call(lambda: service.list_payment_intents(_actor(request), limit=limit, offset=offset))
