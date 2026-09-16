"""Grow account-level webhook payload fixtures, copied verbatim from Grow's
own published documentation at https://developers.grow.business/docs/webhooks
(fetched during this integration's implementation). Field values match the
docs exactly except where noted; nothing here is invented.

Grow's documentation publishes no distinct example for a POS-device or
mobile-app transaction — both are assumed, per this integration's documented
scope, to use the same "Regular Payment Webhook Format via API" shape. See
app/services/ingestion/grow_provider.py's module docstring.
"""

# "Regular Payment Webhook Format via API" — a one-time regular transaction.
GROW_REGULAR_PAYMENT = {
    "webhookKey": "ABC1234",
    "transactionCode": "ABCD1234",
    "transactionType": "אשראי",
    "paymentSum": 2.00,
    "paymentsNum": 1,
    "allPaymentNum": 2,
    "firstPaymentSum": 1,
    "periodicalPaymentSum": 1,
    "paymentType": "רגיל",
    "paymentDate": "14/10/21",
    "asmachta": "123456789",
    "paymentDesc": "Description",
    "fullName": "Full Name",
    "payerPhone": "0500000000",
    "payerEmail": "test@test.com",
    "cardSuffix": "1234",
    "cardBrand": "Mastercard",
    "cardType": "Local",
    "paymentSource": "מערכת חיצונית",
}

# "Multiple Payments Webhook Format via Grow Legacy System" — an
# installment-plan one-time transaction (paymentType="תשלומים"). Per this
# integration's scope, a POS/mobile transaction is assumed to use this same
# account-level shape (see grow_provider.py) — this fixture also stands in
# for that case in tests, since Grow publishes no distinct POS/mobile
# example.
GROW_INSTALLMENTS_PAYMENT = {
    "webhookKey": "ABC1234",
    "transactionCode": "ABCD1235",
    "transactionType": "אשראי",
    "paymentSum": 2.00,
    "paymentsNum": 1,
    "allPaymentNum": 2,
    "firstPaymentSum": 1,
    "periodicalPaymentSum": 1,
    "paymentType": "תשלומים",
    "paymentDate": "28/3/22",
    "asmachta": "123456789",
    "paymentDesc": "Description",
    "fullName": "Full Name",
    "payerPhone": "0500000000",
    "payerEmail": "test@test.com",
    "cardSuffix": "0000",
    "cardBrand": "Visa",
    "cardType": "Local",
    "paymentSource": "עמוד מכירה עסקי",
}

# "Recurring Payment Webhook Format" (paymentType="הוראת קבע") — a
# structurally different Grow webhook (standing order / subscription
# renewal) this integration does not support. Used in tests to confirm it is
# rejected, never silently accepted as a one-time sale.
GROW_RECURRING_PAYMENT_UNSUPPORTED = {
    "webhookKey": "ABC1234",
    "transactionCode": "ABCD9999",
    "transactionType": "אשראי",
    "paymentSum": 8,
    "paymentsNum": 0,
    "allPaymentNum": 1,
    "firstPaymentSum": 0,
    "periodicalPaymentSum": 0,
    "paymentType": "הוראת קבע",
    "paymentDate": "14/10/21",
    "asmachta": "123456789",
    "paymentDesc": "תיאור עסקה",
    "fullName": "Full Name",
    "payerPhone": "0500000000",
    "payerEmail": "test@test.com",
    "cardSuffix": "1234",
    "cardBrand": "Mastercard",
    "cardType": "Local",
    "paymentSource": "ריצת הוראת קבע",
    "directDebitId": "123456",
}

# "Regular Payment Webhook Format via PaymentLinks (New System)" —
# structurally different (transactionId/sum/statusCode), belongs to the
# paid PaymentLinks platform API this integration explicitly does not
# implement. Used in tests to confirm the account-level adapter does not
# accept it either.
GROW_PAYMENT_LINKS_EXCLUDED_FORMAT = {
    "err": "",
    "status": "1",
    "data": {
        "asmachta": "12345",
        "cardSuffix": "1234",
        "cardType": "Local",
        "cardBrand": "Visa",
        "status": "שולם",
        "statusCode": "2",
        "sum": "13",
        "paymentDate": "02/12/24",
        "description": "תיאור עסקה",
        "fullName": "דוד דוד",
        "payerPhone": "0501111111",
        "payerEmail": "test@test.com",
        "transactionId": "1234567",
    },
}

# Grow's separate "Invoice creation" webhook — verbatim shape from
# https://developers.grow.business/docs/webhooks ("Invoice Webhook
# Format"). Uses the same transactionCode as GROW_REGULAR_PAYMENT above so
# tests can exercise correlation between the two deliveries.
GROW_INVOICE_EVENT = {
    "transactionCode": "ABCD1234",
    "invoiceNumber": "20",
    "invoiceUrl": "https://secure.meshulam.co.il",
}
