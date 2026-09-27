"""Payment orchestration foundation — INTENTIONALLY INACTIVE.

This package prepares a provider-agnostic way for Sydney to initiate and
track payments through external providers in the future. Nothing in the
running application uses it:

* it is not imported by ``app.main``, ``app.api.router`` or ``app.models``;
* ``app.payments.router`` is never registered on the production app;
* no real provider adapter exists — only ``FakePaymentProvider``, which
  refuses to run when ``APP_ENVIRONMENT=production``.

It never accepts, stores or logs card numbers, CVV values, track data, bank
credentials or other sensitive payment credentials. It is not PCI-certified
and is not a payment processor. See ``docs/payments-foundation.md``.
"""
