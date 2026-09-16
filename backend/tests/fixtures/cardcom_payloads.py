"""Cardcom fixtures. `CARDCOM_GET_LP_RESULT_SUCCESS` is copied verbatim
(trimmed to the fields this adapter reads) from Cardcom's own published
"GetLpResult" example response at
https://cardcomapi.zendesk.com/hc/he/articles/25264402497426
("שלב 1+2 - יצירת דף לתשלום & שליחת בקשה לקבלת פרטי עסקה") — fetched during
this integration's implementation. `CARDCOM_GET_LP_RESULT_DECLINED` and
`CARDCOM_GET_LP_RESULT_TOKEN_ONLY` are synthesized *within that same
documented field shape* (Cardcom's docs show only a success example) by
changing `TranzactionInfo.ResponseCode` / `Operation` respectively — every
field name and structure is Cardcom's own documented shape, not invented.

Cardcom's raw webhook delivery itself carries no example payload in their
docs beyond "reports transaction details" — this adapter trusts nothing from
it except `LowProfileId` (see cardcom_provider.py's module docstring), so
`CARDCOM_RAW_WEBHOOK_JSON`/`CARDCOM_RAW_WEBHOOK_FORM` are minimal, honestly
representative of that one field, in both of Cardcom's documented content
types (JSON for APILevel 11, form-encoded "Name To Value" for APILevel 10 —
see https://support.cardcom.solutions/hc/he/articles/27875111757970).
"""

CARDCOM_RAW_WEBHOOK_JSON = {
    "TerminalNumber": 1000,
    "LowProfileId": "8c92820a-2f6f-4120-a699-ab1969b2f78b",
}

CARDCOM_RAW_WEBHOOK_FORM = "TerminalNumber=1000&LowProfileId=8c92820a-2f6f-4120-a699-ab1969b2f78b"

# Callback/Name-To-Value terminology observed in Cardcom's documentation
# and in a live declined-payment callback.
CARDCOM_RAW_WEBHOOK_CODE_JSON = {
    "terminalnumber": "1000",
    "LowProfileCode": "declined-lp-id-0001",
}

CARDCOM_GET_LP_RESULT_SUCCESS = {
    "ResponseCode": 0,
    "Description": "העסקה בוצעה בהצלחה",
    "TerminalNumber": 1000,
    "LowProfileId": "8c92820a-2f6f-4120-a699-ab1969b2f78b",
    "TranzactionId": 209413394,
    "ReturnValue": "Z12332X",
    "Operation": "ChargeAndCreateToken",
    "UIValues": {
        "CardOwnerEmail": "testsite@test.co.il",
        "CardOwnerName": "Card Owner",
        "CardOwnerPhone": "039436100",
        "NumOfPayments": 1,
    },
    "TranzactionInfo": {
        "ResponseCode": 0,
        "Description": "העסקה בוצעה בהצלחה",
        "TranzactionId": 209413394,
        "TerminalNumber": 1000,
        "Amount": 10.5,
        "CoinId": 1,
        "CreateDate": "2025-05-06T10:48:21",
        "Last4CardDigits": 0,
        "CardOwnerName": "Card Owner",
        "CardOwnerPhone": "039436100",
        "CardOwnerEmail": "testsite@test.co.il",
        "Brand": "Visa",
        "DealType": "Debit",
        "IsRefund": False,
    },
}

# Same documented shape, ResponseCode changed to a non-zero (declined) value.
CARDCOM_GET_LP_RESULT_DECLINED = {
    "ResponseCode": 0,
    "Description": "העסקה בוצעה בהצלחה",
    "TerminalNumber": 1000,
    "LowProfileId": "declined-lp-id-0001",
    "TranzactionId": None,
    "Operation": "ChargeOnly",
    "TranzactionInfo": {
        "ResponseCode": 3,
        "Description": "כרטיס אשראי לא תקין",
        "TranzactionId": None,
        "TerminalNumber": 1000,
        "Amount": 250.0,
        "CoinId": 1,
        "CreateDate": "2025-05-06T11:02:10",
        "CardOwnerName": "Declined Customer",
        "CardOwnerEmail": "declined@test.co.il",
        "Brand": "Visa",
        "DealType": "Debit",
        "IsRefund": False,
    },
}

# Same documented shape, Operation changed to a non-charging value.
CARDCOM_GET_LP_RESULT_TOKEN_ONLY = {
    "ResponseCode": 0,
    "Description": "העסקה בוצעה בהצלחה",
    "TerminalNumber": 1000,
    "LowProfileId": "token-only-lp-id-0001",
    "Operation": "CreateTokenOnly",
    "TokenInfo": {"Token": "4cf8e168-261e-4613-8d20-000332986b24"},
}

# ResponseCode != 0 at the top level — the GetLpResult call itself failed
# (e.g. an unrecognized LowProfileId), not a real decline.
CARDCOM_GET_LP_RESULT_CALL_FAILED = {
    "ResponseCode": 2,
    "Description": "LowProfileId not found",
}

# Same documented shape as CARDCOM_GET_LP_RESULT_SUCCESS, with the
# documented `DocumentInfo` object added — copied verbatim (trimmed) from
# the same Cardcom example response. `DocumentUrl` is included as `None`
# deliberately: Cardcom's own docs mark that field "לא עובד" (doesn't
# work), so this adapter never reads it either way.
CARDCOM_GET_LP_RESULT_WITH_DOCUMENT_INFO = {
    "ResponseCode": 0,
    "Description": "העסקה בוצעה בהצלחה",
    "TerminalNumber": 1000,
    "LowProfileId": "8c92820a-2f6f-4120-a699-ab1969b2f78b",
    "TranzactionId": 209413394,
    "Operation": "ChargeAndCreateToken",
    "DocumentInfo": {
        "ResponseCode": 0,
        "Description": "העסקה בוצעה בהצלחה",
        "DocumentType": "TaxInvoiceAndReceipt",
        "DocumentNumber": 593032,
        "AccountId": 0,
        "DocumentUrl": None,
    },
    "TranzactionInfo": {
        "ResponseCode": 0,
        "Description": "העסקה בוצעה בהצלחה",
        "TranzactionId": 209413394,
        "TerminalNumber": 1000,
        "Amount": 10.5,
        "CoinId": 1,
        "CreateDate": "2025-05-06T10:48:21",
        "CardOwnerName": "Card Owner",
        "CardOwnerEmail": "testsite@test.co.il",
        "Brand": "Visa",
        "DealType": "Debit",
        "IsRefund": False,
        "DocumentNumber": 593032,
        "DocumentType": "TaxInvoiceAndReceipt",
        "DocumentUrl": None,
    },
}

# A charging operation whose GetLpResult call itself succeeded
# (ResponseCode 0) but whose transaction details aren't resolvable yet —
# TranzactionInfo is entirely absent. Genuinely not yet verifiable (not a
# confirmed decline) — see parse_lowprofile_result's docstring.
CARDCOM_GET_LP_RESULT_NO_TRANZACTION_INFO = {
    "ResponseCode": 0,
    "Description": "העסקה בוצעה בהצלחה",
    "TerminalNumber": 1000,
    "LowProfileId": "not-yet-resolved-lp-id",
    "Operation": "ChargeOnly",
}
