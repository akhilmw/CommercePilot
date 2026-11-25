from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import cast

from openai import OpenAI
from openai.types.responses import ParsedResponse
from pydantic import BaseModel, Field

# Standard USD rates per million tokens: uncached input, cached input, output.
# https://developers.openai.com/api/docs/models/gpt-5-mini
STANDARD_RATES = {
    "gpt-5-mini": (0.25, 0.025, 2.0),
    "gpt-5-mini-2025-08-07": (0.25, 0.025, 2.0),
}


class InputTokenDetails(BaseModel):
    cached_tokens: int = Field(ge=0)


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    input_tokens_details: InputTokenDetails
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


UsageRecord = tuple[TokenUsage, float | None]
_stage_usage: ContextVar[list[UsageRecord] | None] = ContextVar(
    "stage_usage", default=None
)


@contextmanager
def collect_model_usage() -> Iterator[list[UsageRecord]]:
    records: list[UsageRecord] = []
    token = _stage_usage.set(records)
    try:
        yield records
    finally:
        _stage_usage.reset(token)


def parse_model_response[Draft: BaseModel](
    client: OpenAI,
    *,
    model: str,
    instructions: str,
    input: str,
    text_format: type[Draft],
) -> ParsedResponse[Draft]:
    records = _stage_usage.get()
    if records is None:
        return client.responses.parse(
            model=model, instructions=instructions, input=input, text_format=text_format
        )

    raw = client.responses.with_raw_response.parse(
        model=model, instructions=instructions, input=input, text_format=text_format
    )
    # A response can be billable even if structured-output validation fails.
    try:
        payload = raw.http_response.json()
        if isinstance(payload, dict) and payload.get("usage") is not None:
            usage = TokenUsage.model_validate(payload["usage"])
            response_model = payload.get("model")
            rates = (
                STANDARD_RATES.get(response_model)
                if isinstance(response_model, str)
                else None
            )
            estimated_cost = None
            cached = usage.input_tokens_details.cached_tokens
            if (
                rates
                and cached <= usage.input_tokens
                and payload.get("service_tier") in (None, "default", "auto", "standard")
            ):
                estimated_cost = (
                    (usage.input_tokens - cached) * rates[0]
                    + cached * rates[1]
                    + usage.output_tokens * rates[2]
                ) / 1_000_000
            records.append((usage, estimated_cost))
    except ValueError:
        pass  # Usage metadata must never prevent structured-output parsing.
    return cast(ParsedResponse[Draft], raw.parse())


def usage_details(records: Sequence[UsageRecord]) -> dict[str, int | float | None]:
    if not records:
        return {}
    costs = [cost for _, cost in records if cost is not None]
    return {
        "model_responses": len(records),
        "input_tokens": sum(usage.input_tokens for usage, _ in records),
        "cached_input_tokens": sum(
            usage.input_tokens_details.cached_tokens for usage, _ in records
        ),
        "output_tokens": sum(usage.output_tokens for usage, _ in records),
        "total_tokens": sum(usage.total_tokens for usage, _ in records),
        "estimated_cost_usd": (
            round(sum(costs), 9) if len(costs) == len(records) else None
        ),
    }
