"""Subscription billing: trials, entitlements, state machine, gating, webhooks,
provider failures and superadmin overrides. No real provider is contacted:
the only provider used is LocalTestBillingProvider (in-memory)."""

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.api.routes import auth
from app.billing import routes as billing_routes
from app.billing.access import add_months, billing_month, days_remaining, effective_status, evaluate_access
from app.billing.models import (
    BillingCheckoutSession,
    BillingTrialClaim,
    BillingUsageCounter,
    BillingWebhookEvent,
    BusinessSubscription,
    SubscriptionAuditImmutableError,
    SubscriptionEvent,
)
from app.billing.plans import PLANS, TRIAL_DAYS, seed_plan_catalog
from app.billing.providers.base import BillingProviderError, BillingWebhookVerificationError
from app.billing.providers.local_test import LocalTestBillingProvider
from app.billing.service import (
    BillingActor,
    BillingConflictError,
    BillingPermissionError,
    BillingProviderResponseError,
    BillingUnavailable,
    BillingValidationError,
    PlanLimitError,
    QuotaExceededError,
    SubscriptionService,
)
from app.billing.state_machine import InvalidSubscriptionTransition, SubscriptionStatus as S, check_transition
from app.core import tenant  # noqa: F401 - request-scoped tenant guards
from app.core.config import BillingConfigurationError, Settings, get_settings, validate_billing_settings
from app.database import SessionLocal
from app.models.business import AppAccount, Business, BusinessMember
from app.models.integration_connection import IntegrationConnection
from app.models.sale import Sale

A, B = "biz-a-0000-0000-0000-000000000001", "biz-b-0000-0000-0000-000000000002"
NOW = datetime(2026, 9, 27, 9, 0, 0)
SECRET = b"t" * 32


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture
def world():
    with SessionLocal() as db:
        seed_plan_catalog(db)
        db.add_all([Business(id=A, name="Alpha", business_number="514-789-632"), Business(id=B, name="Beta")])
        db.flush()
        db.add_all([
            BusinessMember(business_id=A, user_id="owner-a", role="owner"),
            BusinessMember(business_id=A, user_id="manager-a", role="manager"),
            BusinessMember(business_id=A, user_id="viewer-a", role="viewer"),
            BusinessMember(business_id=B, user_id="owner-b", role="owner"),
        ])
        db.commit()
    provider = LocalTestBillingProvider(environment="development", webhook_secret=SECRET)
    clock = Clock()
    sessions = []

    def service(business_id=A, *, with_provider=True):
        db = SessionLocal()
        if business_id:
            db.info["business_id"] = business_id
        sessions.append(db)
        return SubscriptionService(db, provider=provider if with_provider else None, clock=clock)

    yield {"provider": provider, "clock": clock, "service": service}
    for db in sessions:
        db.close()


def actor(user="owner-a", business=A, role="owner", system_role="user", email=None):
    return BillingActor(user_id=user, business_id=business, business_role=role, system_role=system_role,
                        email=email or f"{user}@example.com")


OWNER_A, OWNER_B = actor(), actor("owner-b", B)
MANAGER_A, VIEWER_A = actor("manager-a", role="manager"), actor("viewer-a", role="viewer")
SUPPORT = actor("staff-1", None, None, "support")
ADMIN = actor("staff-2", None, None, "admin")
SUPERADMIN = actor("staff-3", None, None, "superadmin")


def sub_of(business_id=A) -> BusinessSubscription | None:
    with SessionLocal() as db:
        return db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == business_id))


def events_of(business_id=A) -> list[SubscriptionEvent]:
    with SessionLocal() as db:
        return list(db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.business_id == business_id)
                               .order_by(SubscriptionEvent.sequence)))


def send(world, event_type, *, event_id, **fields):
    ts = int(world["clock"].now.replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": event_id, "type": event_type, "created": ts, **fields}).encode()
    return world["service"](None).receive_webhook("local_test_billing", world["provider"].sign(body, ts), body)


def epoch(moment: datetime) -> int:
    return int(moment.replace(tzinfo=timezone.utc).timestamp())


def activate(world, *, plan="business", interval="month", event_prefix="a"):
    sub = sub_of()
    send(world, "checkout.completed", event_id=f"{event_prefix}-co", subscription_id=sub.id, customer="cus_1", subscription="sub_1")
    start, end = world["clock"].now, add_months(world["clock"].now, 12 if interval == "year" else 1)
    amount = next(p for p in PLANS if p.code == plan)
    return send(world, "invoice.paid", event_id=f"{event_prefix}-inv", subscription_id=sub.id, subscription="sub_1",
                plan=plan, interval=interval, period_start=epoch(start), period_end=epoch(end), currency="ILS",
                amount_excluding_vat=amount.monthly_price_minor if interval == "month" else amount.yearly_price_minor)


# ------------------------------------------------------------ trial rules
def test_trial_starts_for_30_days_from_plan_selection(world):
    sub = world["service"]().start_trial(OWNER_A, "business")
    assert sub.status == S.TRIALING and sub.plan_code == "business"
    assert sub.trial_started_at == NOW and sub.trial_ends_at == NOW + timedelta(days=TRIAL_DAYS)
    assert [e.event_type for e in events_of()] == ["trial_started"]


def test_retrying_onboarding_never_restarts_the_trial(world):
    first = world["service"]().start_trial(OWNER_A, "business")
    world["clock"].now = NOW + timedelta(days=10)
    again = world["service"]().start_trial(OWNER_A, "pro")
    assert again.id == first.id and again.trial_ends_at == first.trial_ends_at and again.plan_code == "business"
    with SessionLocal() as db:
        assert db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == A)) is not None
        assert len(db.scalars(select(BusinessSubscription)).all()) == 1


def test_a_new_business_by_the_same_owner_gets_no_second_trial(world):
    world["service"]().start_trial(OWNER_A, "business")
    # e.g. the owner deleted their account, signed up again and created a new business
    returning = actor("owner-b", B, email="OWNER-A@example.com ")
    sub = world["service"](B).start_trial(returning, "starter")
    assert sub.status == S.EXPIRED and sub.trial_started_at is None and sub.trial_ends_at is None
    assert [e.event_type for e in events_of(B)] == ["trial_unavailable"]


def test_the_same_business_number_gets_no_second_trial(world):
    world["service"]().start_trial(OWNER_A, "business")
    with SessionLocal() as db:
        db.get(Business, B).business_number = "514789632"
        db.commit()
    assert world["service"](B).start_trial(OWNER_B, "starter").status == S.EXPIRED


def test_concurrent_plan_selection_creates_exactly_one_subscription(world, monkeypatch):
    barrier = threading.Barrier(2, timeout=10)
    original = SubscriptionService.subscription_for

    def racing(self, business_id, *, lock=False):
        found = original(self, business_id, lock=lock)
        if found is None and not getattr(threading.current_thread(), "passed", False):
            threading.current_thread().passed = True
            barrier.wait()
        return found

    monkeypatch.setattr(SubscriptionService, "subscription_for", racing)
    results, errors = [], []

    def choose():
        try:
            results.append(world["service"]().start_trial(OWNER_A, "business").id)
        except Exception as error:  # pragma: no cover - reported by the assertion
            errors.append(error)

    threads = [threading.Thread(target=choose) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(results) == 2 and len(set(results)) == 1
    with SessionLocal() as db:
        assert len(db.scalars(select(BusinessSubscription)).all()) == 1
        assert len(db.scalars(select(BillingTrialClaim)).all()) == 2  # email + business number


def test_trial_dates_and_remaining_days():
    end = NOW + timedelta(days=30)
    assert days_remaining(end, NOW) == 30
    assert days_remaining(end, NOW + timedelta(days=29, hours=23)) == 1
    assert days_remaining(end, end) == 0
    assert days_remaining(end, end + timedelta(days=3)) == 0


@pytest.mark.parametrize("anchor,now,start,end", [
    (datetime(2026, 1, 31), datetime(2026, 2, 28, 12), datetime(2026, 2, 28), datetime(2026, 3, 31)),
    (datetime(2026, 1, 31), datetime(2026, 3, 30), datetime(2026, 2, 28), datetime(2026, 3, 31)),
    (datetime(2026, 9, 27, 9), datetime(2026, 9, 27, 9), datetime(2026, 9, 27, 9), datetime(2026, 10, 27, 9)),
    (datetime(2026, 9, 27, 9), datetime(2027, 3, 1), datetime(2027, 2, 27, 9), datetime(2027, 3, 27, 9)),
])
def test_billing_months_are_calendar_months_from_the_anchor(anchor, now, start, end):
    assert billing_month(anchor, now) == (start, end)


# ---------------------------------------------------------- authorization
@pytest.mark.parametrize("who", [MANAGER_A, VIEWER_A, SUPPORT, ADMIN])
def test_only_owners_manage_the_subscription(world, who):
    world["service"]().start_trial(OWNER_A, "business")
    service = world["service"]()
    for call in (
        lambda: service.start_trial(who, "starter"),
        lambda: service.change_plan(who, "pro", "month"),
        lambda: service.set_cancel_at_period_end(who, True),
        lambda: service.create_checkout(who, "business", "month", "idem-key-00001"),
    ):
        with pytest.raises(BillingPermissionError):
            call()


def test_members_can_view_but_support_cannot(world):
    world["service"]().start_trial(OWNER_A, "business")
    view = world["service"]().overview(VIEWER_A)
    assert view["subscription"]["status"] == "trialing" and view["can_manage"] is False
    with pytest.raises(BillingPermissionError):
        world["service"]().overview(SUPPORT)


def test_businesses_never_see_each_others_subscription(world):
    world["service"]().start_trial(OWNER_A, "pro")
    assert world["service"](B).overview(OWNER_B)["subscription"] is None
    # A session scoped to B cannot read A's row even when asked directly.
    assert world["service"](B).subscription_for(A) is None


# ------------------------------------------------------------- entitlements
def test_connection_limit_follows_the_plan(world):
    world["service"](B).start_trial(OWNER_B, "starter")
    world["service"](B).ensure_connection_capacity(B)
    with SessionLocal() as db:
        db.add(IntegrationConnection(business_id=B, provider="demo-pay", name="Till", secret_salt="s"))
        db.commit()
    with pytest.raises(PlanLimitError) as error:
        world["service"](B).ensure_connection_capacity(B)
    assert error.value.allowed == 1 and error.value.current == 1
    world["service"](B).change_plan(OWNER_B, "business", "month")
    world["service"](B).ensure_connection_capacity(B)


def test_downgrade_is_refused_while_usage_exceeds_the_target_plan(world):
    world["service"]().start_trial(OWNER_A, "pro")
    with SessionLocal() as db:
        db.add_all([IntegrationConnection(business_id=A, provider="demo-pay", name=f"Till {i}", secret_salt="s") for i in range(2)])
        db.commit()
    with pytest.raises(PlanLimitError):
        world["service"]().change_plan(OWNER_A, "starter", "month")
    assert sub_of().plan_code == "pro"


def test_member_limit_is_enforced(world):
    # Business A already has 3 members, so it cannot choose Starter (1 member).
    with pytest.raises(PlanLimitError) as error:
        world["service"]().start_trial(OWNER_A, "starter")
    assert error.value.limit == "members" and sub_of() is None
    # Business B has exactly its Starter allowance: the next member is refused.
    world["service"](B).start_trial(OWNER_B, "starter")
    with pytest.raises(PlanLimitError):
        world["service"](B).ensure_member_capacity(B)
    world["service"](B).change_plan(OWNER_B, "business", "month")
    world["service"](B).ensure_member_capacity(B)


def test_ai_questions_are_limited_per_billing_month(world):
    world["service"](B).start_trial(OWNER_B, "starter")
    counter_id = world["service"](B).reserve_ai_question(B)
    with SessionLocal() as db:
        db.execute(update(BillingUsageCounter).where(BillingUsageCounter.id == counter_id).values(used=300))
        db.commit()
    with pytest.raises(QuotaExceededError):
        world["service"](B).reserve_ai_question(B)
    # The next billing month starts fresh.
    world["clock"].now = add_months(NOW, 1) + timedelta(minutes=1)
    assert world["service"](B).reserve_ai_question(B) != counter_id


def test_ai_question_is_released_when_the_answer_fails(world):
    world["service"](B).start_trial(OWNER_B, "starter")
    service = world["service"](B)
    counter_id = service.reserve_ai_question(B)
    service.release_ai_question(counter_id)
    with SessionLocal() as db:
        assert db.get(BillingUsageCounter, counter_id).used == 0


def test_concurrent_ai_questions_never_exceed_the_quota(world):
    world["service"](B).start_trial(OWNER_B, "starter")
    counter_id = world["service"](B).reserve_ai_question(B)
    with SessionLocal() as db:
        db.execute(update(BillingUsageCounter).where(BillingUsageCounter.id == counter_id).values(used=295))
        db.commit()
    outcomes = []

    def ask():
        try:
            world["service"](B).reserve_ai_question(B)
            outcomes.append("ok")
        except QuotaExceededError:
            outcomes.append("limit")

    threads = [threading.Thread(target=ask) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert outcomes.count("ok") == 5
    with SessionLocal() as db:
        assert db.get(BillingUsageCounter, counter_id).used == 300


# ---------------------------------------------------------- state machine
@pytest.mark.parametrize("current,target", [
    (S.TRIALING, S.ACTIVE), (S.TRIALING, S.PAST_DUE), (S.TRIALING, S.EXPIRED), (S.ACTIVE, S.PAST_DUE),
    (S.ACTIVE, S.CANCELED), (S.PAST_DUE, S.ACTIVE), (S.PAST_DUE, S.CANCELED), (S.EXPIRED, S.ACTIVE), (S.CANCELED, S.ACTIVE),
])
def test_allowed_subscription_transitions(current, target):
    assert check_transition(current, target)


@pytest.mark.parametrize("current,target", [
    (S.ACTIVE, S.TRIALING), (S.EXPIRED, S.TRIALING), (S.CANCELED, S.TRIALING), (S.ACTIVE, S.EXPIRED),
    (S.EXPIRED, S.PAST_DUE), (S.CANCELED, S.EXPIRED), (S.PAST_DUE, S.TRIALING),
])
def test_illegal_subscription_transitions(current, target):
    with pytest.raises(InvalidSubscriptionTransition):
        check_transition(current, target)


def test_only_overrides_may_reopen_a_trial():
    assert check_transition(S.EXPIRED, S.TRIALING, override=True)
    with pytest.raises(InvalidSubscriptionTransition):
        check_transition(S.ACTIVE, S.TRIALING, override=True)


def test_trial_expiry_is_time_based_and_then_persisted(world):
    world["service"]().start_trial(OWNER_A, "business")
    sub = sub_of()
    assert evaluate_access(sub, NOW + timedelta(days=29)).allowed
    decision = evaluate_access(sub, NOW + timedelta(days=30))
    assert not decision.allowed and decision.reason == "trial_expired"
    world["clock"].now = NOW + timedelta(days=31)
    overview = world["service"]().overview(OWNER_A)
    assert overview["subscription"]["status"] == "expired" and overview["access"]["reason"] == "trial_expired"
    assert [e.event_type for e in events_of()][-1] == "lapsed"


# ------------------------------------------------------------ cancellation
def test_cancelling_during_the_trial_ends_it_at_the_trial_end_without_charging(world):
    world["service"]().start_trial(OWNER_A, "business")
    sub = world["service"]().set_cancel_at_period_end(OWNER_A, True)
    assert sub.cancel_at_period_end and sub.status == S.TRIALING
    assert evaluate_access(sub_of(), NOW + timedelta(days=29)).allowed
    assert effective_status(sub_of(), NOW + timedelta(days=30)) == S.EXPIRED
    assert world["service"]().set_cancel_at_period_end(OWNER_A, False).cancel_at_period_end is False


def test_cancelling_a_paid_subscription_takes_effect_at_period_end(world):
    world["service"]().start_trial(OWNER_A, "business")
    activate(world)
    sub = world["service"]().set_cancel_at_period_end(OWNER_A, True)
    assert ("set_cancel_at_period_end", "sub_1", True) in world["provider"].calls
    period_end = sub.current_period_end
    assert evaluate_access(sub_of(), period_end - timedelta(minutes=1)).allowed
    assert effective_status(sub_of(), period_end) == S.CANCELED
    send(world, "subscription.canceled", event_id="end-1", subscription_id=sub.id, subscription="sub_1")
    ended = sub_of()
    assert ended.status == S.CANCELED and not evaluate_access(ended, period_end).allowed


def test_provider_failure_leaves_renewal_unchanged(world):
    world["service"]().start_trial(OWNER_A, "business")
    activate(world)
    world["provider"].fail_next["set_cancel_at_period_end"] = BillingProviderError("timeout", retryable=True)
    with pytest.raises(BillingProviderError):
        world["service"]().set_cancel_at_period_end(OWNER_A, True)
    assert sub_of().cancel_at_period_end is False


# ---------------------------------------------------------------- webhooks
def test_payment_confirms_the_subscription_only_through_a_verified_webhook(world):
    world["service"]().start_trial(OWNER_A, "business")
    checkout = world["service"]().create_checkout(OWNER_A, "business", "month", "idem-key-00001")
    assert checkout.checkout_url.startswith("https://checkout.local-test-billing.invalid/")
    assert sub_of().status == S.TRIALING  # a checkout URL is not a payment
    outcome = activate(world)
    assert outcome.status == "processed"
    sub = sub_of()
    assert sub.status == S.ACTIVE and sub.payment_method_on_file and sub.current_period_end == add_months(NOW, 1)


def test_checkout_during_the_trial_tells_the_provider_not_to_charge_before_it_ends(world):
    world["service"]().start_trial(OWNER_A, "business")
    world["service"]().create_checkout(OWNER_A, "business", "year", "idem-key-00001")
    call = next(c for c in world["provider"].calls if c[0] == "create_checkout_session")
    assert call[3] == "year" and call[4] == NOW + timedelta(days=30)


def test_checkout_is_idempotent(world):
    world["service"]().start_trial(OWNER_A, "business")
    first = world["service"]().create_checkout(OWNER_A, "business", "month", "idem-key-00001")
    again = world["service"]().create_checkout(OWNER_A, "business", "month", "idem-key-00001")
    assert first.id == again.id
    with pytest.raises(BillingConflictError):
        world["service"]().create_checkout(OWNER_A, "pro", "month", "idem-key-00001")


def test_duplicate_webhooks_are_recorded_once(world):
    world["service"]().start_trial(OWNER_A, "business")
    activate(world)
    before = len(events_of())
    again = activate(world)  # same event ids delivered again
    assert again.status == "processed"
    with SessionLocal() as db:
        assert len(db.scalars(select(BillingWebhookEvent)).all()) == 2
    assert len(events_of()) == before


def test_unverified_webhooks_are_rejected_and_not_stored(world, caplog):
    world["service"]().start_trial(OWNER_A, "business")
    body = json.dumps({"id": "forged", "type": "invoice.paid", "created": epoch(NOW)}).encode()
    headers = {"x-local-test-billing-signature": "0" * 64, "x-local-test-billing-timestamp": str(epoch(NOW)),
               "authorization": "Bearer super-secret"}
    with pytest.raises(BillingWebhookVerificationError):
        world["service"](None).receive_webhook("local_test_billing", headers, body)
    with SessionLocal() as db:
        assert db.scalars(select(BillingWebhookEvent)).all() == []
    assert "super-secret" not in caplog.text and "forged" not in caplog.text
    assert sub_of().status == S.TRIALING


def test_charge_for_the_wrong_amount_is_not_accepted(world):
    world["service"]().start_trial(OWNER_A, "business")
    sub = sub_of()
    outcome = send(world, "invoice.paid", event_id="bad", subscription_id=sub.id, plan="business", interval="month",
                   period_start=epoch(NOW), period_end=epoch(add_months(NOW, 1)), currency="ILS", amount_excluding_vat=100)
    assert outcome.status == "ignored" and sub_of().status == S.TRIALING


def test_failed_renewal_moves_to_past_due_and_recovers(world):
    world["service"]().start_trial(OWNER_A, "business")
    activate(world)
    sub = sub_of()
    send(world, "invoice.payment_failed", event_id="f1", subscription_id=sub.id, failure_reason="card 4242424242424242 declined")
    assert sub_of().status == S.PAST_DUE
    assert evaluate_access(sub_of(), NOW + timedelta(days=5)).reason == "past_due"
    with SessionLocal() as db:
        stored = db.scalar(select(BillingWebhookEvent).where(BillingWebhookEvent.provider_event_id == "f1"))
    assert "4242424242424242" not in json.dumps(stored.payload_summary)
    world["clock"].now = add_months(NOW, 1)
    activate(world, event_prefix="b")
    assert sub_of().status == S.ACTIVE


def test_events_for_another_provider_subscription_are_ignored(world):
    world["service"]().start_trial(OWNER_A, "business")
    activate(world)
    sub = sub_of()
    outcome = send(world, "subscription.canceled", event_id="x1", subscription_id=sub.id, subscription="sub_someone_else")
    assert outcome.status == "ignored" and sub_of().status == S.ACTIVE


def test_out_of_order_webhook_is_recorded_but_not_applied(world):
    world["service"]().start_trial(OWNER_A, "business")
    world["clock"].now = NOW + timedelta(days=40)
    world["service"]().overview(OWNER_A)  # persists expired
    outcome = send(world, "invoice.payment_failed", event_id="late", subscription_id=sub_of().id)
    assert outcome.status == "ignored" and "Out-of-order" in outcome.last_error


def test_transient_processing_failure_is_recorded_and_retried_on_redelivery(world, monkeypatch):
    world["service"]().start_trial(OWNER_A, "business")
    original = SubscriptionService._apply
    state = {"fail": True}

    def flaky(self, *args):
        if state.pop("fail", False):
            raise RuntimeError("database is locked")
        return original(self, *args)

    monkeypatch.setattr(SubscriptionService, "_apply", flaky)
    sub = sub_of()
    first = send(world, "checkout.completed", event_id="co-1", subscription_id=sub.id, subscription="sub_1")
    assert first.status == "failed" and first.attempt_count == 1
    again = send(world, "checkout.completed", event_id="co-1", subscription_id=sub.id, subscription="sub_1")
    assert again.status == "processed" and again.attempt_count == 2 and sub_of().payment_method_on_file


# --------------------------------------------------------- provider failures
def test_no_provider_means_checkout_is_unavailable_not_faked(world):
    world["service"]().start_trial(OWNER_A, "business")
    with pytest.raises(BillingUnavailable):
        world["service"](with_provider=False).create_checkout(OWNER_A, "business", "month", "idem-key-00001")
    with SessionLocal() as db:
        assert db.scalars(select(BillingCheckoutSession)).all() == []


def test_provider_errors_leave_no_checkout_behind(world):
    world["service"]().start_trial(OWNER_A, "business")
    world["provider"].fail_next["create_checkout_session"] = BillingProviderError("down", retryable=True)
    with pytest.raises(BillingProviderError):
        world["service"]().create_checkout(OWNER_A, "business", "month", "idem-key-00001")
    with SessionLocal() as db:
        assert db.scalars(select(BillingCheckoutSession)).all() == []


def test_untrusted_checkout_urls_are_refused(world, monkeypatch):
    world["service"]().start_trial(OWNER_A, "business")
    from app.billing.providers.base import CheckoutSession

    monkeypatch.setattr(world["provider"], "create_checkout_session",
                        lambda request: CheckoutSession("cs_1", "https://evil.example/pay"))
    with pytest.raises(BillingProviderResponseError):
        world["service"]().create_checkout(OWNER_A, "business", "month", "idem-key-00001")


# ----------------------------------------------------------- admin overrides
def test_superadmin_can_extend_an_expired_trial_with_an_audited_reason(world):
    world["service"]().start_trial(OWNER_A, "business")
    world["clock"].now = NOW + timedelta(days=35)
    sub = world["service"](None).admin_override(SUPERADMIN, A, action="extend_trial", days=14, reason="Onboarding call delayed")
    assert sub.status == S.TRIALING and sub.trial_ends_at == NOW + timedelta(days=49)
    last = events_of()[-1]
    assert last.source == "admin" and last.actor_user_id == "staff-3" and last.reason == "Onboarding call delayed"


@pytest.mark.parametrize("who", [OWNER_A, SUPPORT, ADMIN])
def test_only_superadmins_override(world, who):
    world["service"]().start_trial(OWNER_A, "business")
    with pytest.raises(BillingPermissionError):
        world["service"](None).admin_override(who, A, action="extend_trial", days=5, reason="Please extend it")


def test_overrides_require_a_reason_and_valid_values(world):
    world["service"]().start_trial(OWNER_A, "business")
    with pytest.raises(BillingValidationError):
        world["service"](None).admin_override(SUPERADMIN, A, action="extend_trial", days=5, reason="  ")
    with pytest.raises(BillingValidationError):
        world["service"](None).admin_override(SUPERADMIN, A, action="extend_trial", days=365, reason="Too generous")


def test_granted_access_is_complimentary_and_does_not_renew(world):
    world["service"]().start_trial(OWNER_A, "business")
    until = NOW + timedelta(days=60)
    sub = world["service"](None).admin_override(SUPERADMIN, A, action="grant_access", until=until, reason="Partner account")
    assert sub.status == S.ACTIVE and sub.cancel_at_period_end and sub.current_period_end == until
    assert effective_status(sub_of(), until) == S.CANCELED


def test_support_and_admin_can_view_subscriptions(world):
    world["service"]().start_trial(OWNER_A, "business")
    rows = world["service"](None).admin_list(SUPPORT)
    row = next(r for r in rows if r["business_id"] == A)
    assert row["status"] == "trialing" and row["access_allowed"] is True
    assert [e.event_type for e in world["service"](None).admin_events(ADMIN, A)] == ["trial_started"]


def test_subscription_history_is_append_only(world):
    world["service"]().start_trial(OWNER_A, "business")
    with SessionLocal() as db:
        event = db.scalar(select(SubscriptionEvent))
        event.reason = "rewritten"
        with pytest.raises(SubscriptionAuditImmutableError):
            db.commit()


# ----------------------------------------------------- configuration safety
def test_production_refuses_the_local_test_provider():
    with pytest.raises(BillingConfigurationError):
        validate_billing_settings(Settings(app_environment="production", billing_provider="local_test",
                                           billing_local_test_webhook_secret="x" * 40))
    with pytest.raises(RuntimeError):
        LocalTestBillingProvider(environment="production", webhook_secret=SECRET)


def test_production_refuses_enforcement_without_a_provider():
    with pytest.raises(BillingConfigurationError):
        validate_billing_settings(Settings(app_environment="production", billing_enforcement_enabled=True))
    validate_billing_settings(Settings(app_environment="production"))  # the safe default


# --------------------------------------------------------------- HTTP layer
@pytest.fixture
def http(world, monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    with SessionLocal() as db:
        for user, role in [("owner-a", "user"), ("owner-b", "user"), ("staff-3", "superadmin"), ("staff-2", "admin")]:
            db.add(AppAccount(user_id=user, email=f"{user}@example.com", system_role=role))
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {"id": token, "email": f"{token}@example.com", "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", fake_auth)
    return client


def call(client, method, path, user, **kwargs):
    client.cookies.set("sydney_access", user)
    return client.request(method, path, headers={"origin": "http://localhost:5174", **kwargs.pop("headers", {})}, **kwargs)


def test_public_plan_catalog_needs_no_login(http):
    http.cookies.clear()
    response = http.get("/api/billing/plans")
    assert response.status_code == 200
    body = response.json()
    assert [p["code"] for p in body["plans"]] == ["starter", "business", "pro"]
    business = body["plans"][1]
    assert business["recommended"] and business["prices"] == {"month": 11_900, "year": 119_000}
    assert body["prices_exclude_vat"] is True and body["member_limits_available"] is False


def test_expired_trial_blocks_the_product_but_not_billing_or_support(http, world, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_enforcement_enabled", True)
    assert call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business"}).status_code == 201
    assert call(http, "GET", "/api/sales", "owner-a").status_code == 200
    with SessionLocal() as db:
        sub = db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == A))
        sub.trial_started_at, sub.trial_ends_at = datetime.utcnow() - timedelta(days=40), datetime.utcnow() - timedelta(days=10)
        db.add(Sale(business_id=A, customer_name="Kept", service_name="Data", gross_amount=100, net_amount=84))
        db.commit()
    blocked = call(http, "GET", "/api/sales", "owner-a")
    assert blocked.status_code == 402 and blocked.json()["code"] == "subscription_required"
    assert blocked.json()["reason"] == "trial_expired"
    overview = call(http, "GET", "/api/billing/subscription", "owner-a")
    assert overview.status_code == 200 and overview.json()["enforcement_enabled"] is True
    assert overview.json()["access"] == {"allowed": False, "reason": "trial_expired"}
    assert call(http, "GET", "/api/support/requests", "owner-a").status_code == 200
    with SessionLocal() as db:  # nothing was deleted
        assert db.scalar(select(Sale).where(Sale.business_id == A, Sale.customer_name == "Kept")) is not None


def test_no_lockout_while_enforcement_is_off(http):
    assert call(http, "GET", "/api/sales", "owner-b").status_code == 200  # no plan chosen yet
    assert call(http, "GET", "/api/billing/subscription", "owner-b").json()["enforcement_enabled"] is False


def test_connection_limit_is_enforced_by_the_api(http, monkeypatch):
    monkeypatch.setattr(get_settings(), "connection_signing_secret", "test-master-key-with-at-least-32-characters")
    call(http, "POST", "/api/billing/trial", "owner-b", json={"plan_code": "starter"})
    first = call(http, "POST", "/api/connections", "owner-b", json={"name": "Till", "provider": "demo-pay"})
    assert first.status_code == 201
    second = call(http, "POST", "/api/connections", "owner-b", json={"name": "Till 2", "provider": "demo-pay"})
    assert second.status_code == 403 and second.json()["detail"]["limit"] == "connections"


def test_assistant_quota_is_enforced_by_the_api(http, monkeypatch):
    from app.api.routes import assistant as assistant_routes

    monkeypatch.setattr(assistant_routes, "answer_question", lambda *args, **kwargs: "תשובה")
    call(http, "POST", "/api/billing/trial", "owner-b", json={"plan_code": "starter"})
    assert call(http, "POST", "/api/assistant/chat", "owner-b", json={"message": "כמה הכנסתי?"}).status_code == 200
    with SessionLocal() as db:
        db.execute(update(BillingUsageCounter).values(used=300))
        db.commit()
    limited = call(http, "POST", "/api/assistant/chat", "owner-b", json={"message": "ועוד שאלה"})
    assert limited.status_code == 429 and "300" in limited.json()["detail"]


def test_request_schemas_reject_unknown_fields(http):
    response = call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business", "card_number": "4242424242424242"})
    assert response.status_code == 422


def test_checkout_without_a_provider_answers_503(http):
    call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business"})
    response = call(http, "POST", "/api/billing/checkout", "owner-a", json={"plan_code": "business"},
                    headers={"Idempotency-Key": "idem-key-00001"})
    assert response.status_code == 503


def test_admin_override_endpoint_requires_superadmin(http):
    call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business"})
    body = {"action": "extend_trial", "days": 7, "reason": "Customer asked for more time"}
    assert call(http, "POST", f"/api/support/staff/billing/subscriptions/{A}/overrides", "staff-2", json=body).status_code == 403
    ok = call(http, "POST", f"/api/support/staff/billing/subscriptions/{A}/overrides", "staff-3", json=body)
    assert ok.status_code == 200
    listing = call(http, "GET", "/api/support/staff/billing/subscriptions", "staff-2")
    assert listing.status_code == 200 and any(r["business_id"] == A for r in listing.json())


def test_billing_webhook_endpoint_is_separate_and_verified(http, monkeypatch, world):
    monkeypatch.setattr(get_settings(), "billing_provider", "local_test")
    monkeypatch.setattr(get_settings(), "billing_local_test_webhook_secret", SECRET.decode())
    call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business"})
    http.cookies.clear()
    forged = http.post("/api/billing/webhooks/local_test_billing", content=b'{"id":"x"}', headers={"content-type": "application/json"})
    assert forged.status_code == 400
    sub = sub_of()
    ts = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": "ev-http", "type": "checkout.completed", "created": ts, "subscription_id": sub.id,
                       "subscription": "sub_http"}).encode()
    good = http.post("/api/billing/webhooks/local_test_billing", content=body, headers={**world["provider"].sign(body, ts)})
    assert good.status_code == 200 and sub_of().payment_method_on_file
    # The customer-sales webhook path is a different endpoint entirely.
    assert http.post("/api/webhooks/connections/" + "a" * 32, content=body).status_code != 200


def test_support_is_not_ranked_by_subscription_plan(http):
    call(http, "POST", "/api/billing/trial", "owner-a", json={"plan_code": "business"})
    call(http, "POST", "/api/billing/trial", "owner-b", json={"plan_code": "starter"})
    for user in ("owner-a", "owner-b"):
        assert call(http, "POST", "/api/support/requests", user,
                    json={"subject": "עזרה בחיבור", "message": "צריך עזרה בחיבור של הקופה"}).status_code == 201
    rows = call(http, "GET", "/api/support/staff/requests", "staff-2").json()
    assert {r["business_id"] for r in rows} == {A, B}
    assert all("priority" not in r for r in rows)
    own = call(http, "GET", "/api/support/requests", "owner-a").json()
    assert all("priority" not in r for r in own)


def test_plans_in_code_match_the_seeded_catalog(world):
    with SessionLocal() as db:
        from app.billing.service import plan_catalog

        catalog = {p["code"]: p for p in plan_catalog(db)}
    for plan in PLANS:
        row = catalog[plan.code]
        assert row["prices"] == {"month": plan.monthly_price_minor, "year": plan.yearly_price_minor}
        assert (row["max_connections"], row["max_members"], row["ai_questions_per_month"]) == (
            plan.max_connections, plan.max_members, plan.ai_questions_per_month)
    assert billing_routes.router.prefix == "/billing"


def test_assistant_question_that_gets_no_answer_is_not_counted(http, monkeypatch):
    from app.api.routes import assistant as assistant_routes
    from app.services.assistant.exceptions import AssistantProviderError

    def failing(*args, **kwargs):
        raise AssistantProviderError("model unavailable")

    monkeypatch.setattr(assistant_routes, "answer_question", failing)
    call(http, "POST", "/api/billing/trial", "owner-b", json={"plan_code": "starter"})
    assert call(http, "POST", "/api/assistant/chat", "owner-b", json={"message": "שאלה"}).status_code == 503
    assert call(http, "POST", "/api/assistant/chat", "owner-b",
                json={"message": "שאלה", "conversation_id": "missing"}).status_code == 404
    with SessionLocal() as db:
        assert [c.used for c in db.scalars(select(BillingUsageCounter))] == [0]
