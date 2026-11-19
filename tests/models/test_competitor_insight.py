from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.competitor import CompetitorFinding
from commercepilot.models.enums import CompetitiveThreatLevel


def test_competitor_finding_requires_snapshot_evidence() -> None:
    with pytest.raises(ValidationError):
        CompetitorFinding(
            competitor_product_id=uuid4(),
            competitor_name="AudioPeak",
            threat_level=CompetitiveThreatLevel.HIGH,
            summary="AudioPeak has created meaningful pricing pressure.",
            evidence_snapshot_ids=[],
        )
