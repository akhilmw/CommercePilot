from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from commercepilot.core.model_usage import (
    collect_model_usage,
    parse_model_response,
    usage_details,
)


class Draft(BaseModel):
    title: str


@pytest.mark.parametrize(
    ("model", "cost"),
    [("gpt-5-mini-2025-08-07", 0.00081), ("unpriced-model", None)],
)
def test_usage_counts_a_rejected_draft_and_its_retry(
    model: str, cost: float | None
) -> None:
    client = MagicMock()
    raw = client.responses.with_raw_response.parse.return_value
    raw.http_response.json.return_value = {
        "model": model,
        "usage": {
            "input_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 200},
            "output_tokens": 100,
            "total_tokens": 1100,
        },
    }
    with pytest.raises(ValidationError) as invalid:
        Draft.model_validate({})
    raw.parse.side_effect = [invalid.value, MagicMock()]
    request = {
        "model": model,
        "instructions": "Write a title.",
        "input": "Product",
    }

    with collect_model_usage() as usage:
        with pytest.raises(ValidationError):
            parse_model_response(client, **request, text_format=Draft)
        parse_model_response(client, **request, text_format=Draft)

    assert usage_details(usage) == {
        "model_responses": 2,
        "input_tokens": 2000,
        "cached_input_tokens": 400,
        "output_tokens": 200,
        "total_tokens": 2200,
        "estimated_cost_usd": cost,
    }

    parse_model_response(client, **request, text_format=Draft)
    client.responses.parse.assert_called_once()
