"""Runs a bounded OpenAI tool-calling conversation turn over the read-only
assistant tools (see tools.py). The model never sees the database schema or
writes any query itself — it only ever picks from the fixed TOOL_DEFINITIONS
list, and every tool call is dispatched through TOOL_FUNCTIONS, the same
lookup table the model's own tool definitions were generated from."""

import json
import logging
from datetime import date

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.business_time import business_today
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

def _system_prompt(today: date) -> str:
    # The model's own training data has a cutoff far earlier than "today" can
    # be, so without this it will happily guess a wrong year (and silently
    # compute an empty date range) whenever a relative phrase like "this
    # month"/"today"/"this week" needs resolving — this must be told, never
    # assumed.
    return (
        f"Today's date is {today.isoformat()} (the business's own Israel calendar date, Asia/Jerusalem — not "
        "UTC). When the user asks about 'this month', 'today', 'this week', or any other relative period, "
        "compute the actual start_date/end_date from that real date yourself — never guess or assume a "
        "different year.\n\n"
        "You are a helpful assistant for a small business owner using Sydney Transaction Management, a sales "
        "and revenue management app. Answer questions about their sales, customers, revenue, VAT, processing "
        "fees, refunds, and customer receipt/invoice status using only the provided tools — never invent a "
        "number. If a tool returns no data for the question asked, say so honestly rather than guessing. Every "
        "question about the business's current data must use a tool in that turn, even if an earlier chat message "
        "already mentioned a number: stored chat history can be stale, while the database is the source of truth.\n\n"
        "Choose tools by the subject of the question, not just by similar words. A 'sale', 'transaction', or "
        "'payment' in the singular means an individual row: use query_sales. For the largest/highest transaction "
        "amount (including Hebrew phrasing such as 'המכירה הכי גבוהה', 'איזו עסקה עשתה הכי הרבה כסף', or "
        "'התשלום הגדול ביותר'), use gross_amount descending unless the user explicitly asks for net revenue. A "
        "customer, service, payment method, day, week, or month that generated the most is a grouped question: "
        "use analyze_sales with the matching group_by. Use analyze_sales for averages and breakdowns, and "
        "compare_sales_periods for comparisons between two periods. Use query_sales for filtered lists and top or "
        "bottom individual transactions. Do not substitute get_top_services for an individual-sale question. "
        "When an ordinary business phrase has a conventional meaning, use that meaning and briefly name the "
        "metric in the answer instead of asking an unnecessary clarification. Ask a short clarifying question only "
        "when two materially different interpretations remain.\n\n"
        "Be precise about money: 'gross revenue' is what customers paid before VAT and processing fees are "
        "subtracted; 'net revenue' (gross minus VAT minus fees minus any refund) is what the business actually "
        "keeps; neither is the same as accounting profit. If asked something like 'how much did I profit' or "
        "'כמה הרווחתי', answer with the net or gross revenue you actually have data for, name which one you're "
        "giving, and say plainly that true profit would also require the business's own expenses, which this "
        "assistant does not have data on — never call a revenue figure 'profit'. Reflect refunds accurately: a "
        "refunded sale contributes nothing to revenue, a partially refunded one only its remaining net amount.\n\n"
        "Currency: this business is Israeli, but a sale can be charged in ILS, USD, or EUR — currency is never "
        "the same thing as which tax rules apply, and every tool response below tells you the currency of every "
        "number it returns (a '..._by_currency' list, or a 'currency' field on each row). You must use ONLY the "
        "currency a tool actually returned — never guess, assume, or default to one. When answering in Hebrew "
        "about an ILS amount, show ₪ or the word 'שקלים'/'ILS' — never a $ sign. When an amount is in USD, show $ "
        "or 'USD'; when in EUR, show € or 'EUR'. If a tool's result contains more than one currency for the same "
        "question (e.g. some sales in ILS and some in USD), report each currency's total separately and clearly "
        "labeled — never add them together into one number, and never pick just one and drop the other silently. "
        "If a currency breakdown has only one entry, just report that one figure with its currency.\n\n"
        "Reply in the same language the user asked in (Hebrew or English). Keep answers concise and "
        "conversational, formatted for a chat bubble, not a report."
    )

_MAX_TOOL_ROUNDS = 5

_TRANSIENT_TIMEOUT_ERRORS = (APITimeoutError,)
_TRANSIENT_RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)
_NON_TRANSIENT_ERRORS = (BadRequestError, AuthenticationError, PermissionDeniedError, NotFoundError)


def answer_question(
    settings: Settings,
    db: Session,
    message: str,
    history: list[dict[str, str]],
    client: OpenAI | None = None,
    today: date | None = None,
) -> str:
    if not settings.openai_api_key:
        raise AssistantConfigError("OPENAI_API_KEY is not configured.")
    if client is None:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=0)

    # Never the server's OS timezone or a bare UTC date — see
    # app.domain.business_time for why that distinction matters here.
    messages: list[dict] = [{"role": "system", "content": _system_prompt(today or business_today())}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    for _round in range(_MAX_TOOL_ROUNDS):
        message_out = _create_completion(client, settings, messages, with_tools=True)

        if not message_out.tool_calls:
            return message_out.content or ""

        messages.append(_assistant_message_dict(message_out))
        for tool_call in message_out.tool_calls:
            result = _run_tool(db, tool_call.function.name, tool_call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

    # Hard cap reached: ask once more without tools, forcing a text answer
    # from whatever's already been gathered, rather than looping forever.
    final = _create_completion(client, settings, messages, with_tools=False)
    return final.content or "לא הצלחתי למצוא תשובה מלאה לשאלה הזו."


def _assistant_message_dict(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        if message.tool_calls
        else None,
    }


def _create_completion(client: OpenAI, settings: Settings, messages: list[dict], *, with_tools: bool):
    try:
        response = client.chat.completions.create(
            model=settings.openai_assistant_model,
            messages=messages,
            tools=TOOL_DEFINITIONS if with_tools else None,
            timeout=settings.openai_timeout_seconds,
        )
        return response.choices[0].message
    except _TRANSIENT_TIMEOUT_ERRORS as exc:
        raise AssistantProviderError("Assistant request timed out.") from exc
    except _TRANSIENT_RETRYABLE_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider failed: {type(exc).__name__}") from exc
    except _NON_TRANSIENT_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider error: {type(exc).__name__}") from exc


def _run_tool(db: Session, name: str, arguments_json: str) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return {"error": "invalid tool arguments"}
    try:
        return func(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a tool error must reach the model as data, not crash the request
        logger.info("assistant_tool_error tool=%s error_category=%s", name, type(exc).__name__)
        return {"error": f"tool failed: {type(exc).__name__}"}
