"""The single source of truth for this demo's fixed business profile.

This app currently has no authentication, registration, or multi-business
support (deliberately, for this phase) — every sale belongs to one fixed
fictional Israeli business. Every value a real deployment would eventually
store per-business (country, tax jurisdiction, reporting currency, timezone,
standard VAT rate, default transaction currency) lives here, in exactly one
place, rather than as scattered literals across models/schemas/services.
Replacing this module's contents with a per-business database row is the
intended extension point for real multi-business support later — nothing
outside this module should ever hardcode "IL", "ILS", or "0.18" again.
"""

from decimal import Decimal

DEMO_BUSINESS_NAME = "Sydney Demo Business (Israel)"

# ISO 3166-1 alpha-2. The business's country of operation, and separately the
# jurisdiction whose tax rules apply — kept as two named constants (even
# though they're equal today) because a real business could legally operate
# in one country while being taxed in another, and currency must never be
# confused with either: an Israeli business charging in USD is still an
# Israeli business, taxed under Israeli VAT rules, see calculate_vat below.
DEMO_BUSINESS_COUNTRY = "IL"
DEMO_TAX_JURISDICTION = "IL"

# IANA timezone name. Used for "this month"/"today" reporting-period
# boundaries once a per-business timezone is wired through the dashboard —
# not yet consumed everywhere calendar boundaries are computed (see
# dashboard_service.py), but defined here now so that wiring has one place to
# read from instead of a second hardcoded literal appearing later.
DEMO_TIMEZONE = "Asia/Jerusalem"

# The currency financial totals are reported in when multiple transaction
# currencies can't be summed together (see dashboard_service.py and
# assistant/tools.py) — distinct from DEMO_DEFAULT_TRANSACTION_CURRENCY,
# which is just the currency a new sale defaults to in the form.
DEMO_REPORTING_CURRENCY = "ILS"
DEMO_DEFAULT_TRANSACTION_CURRENCY = "ILS"

# The Israeli standard VAT rate currently in effect for this demo. A real
# business would need this to be able to change over time (Israel's own
# standard rate has changed before); this app doesn't model that history yet,
# which is exactly why every sale snapshots the rate it was actually
# calculated with onto Sale.vat_rate — see app/services/tax/vat.py — so a
# future change to this constant can never silently rewrite a past sale's
# VAT.
DEMO_STANDARD_VAT_RATE = Decimal("0.18")

# The closed set of transaction currencies selectable through the manual Sale
# form (see app.models.sale.SaleCurrency). Webhook and CSV ingestion are
# intentionally NOT restricted to this set — a real payment provider or bank
# export may legitimately use a currency this demo's UI doesn't offer yet.
DEMO_SUPPORTED_TRANSACTION_CURRENCIES = ("ILS", "USD", "EUR")
