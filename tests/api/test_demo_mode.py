from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from commercepilot.core.config import get_settings
from commercepilot.main import app

client = TestClient(app)


@pytest.fixture
def demo_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("COMMERCEPILOT_READ_ONLY_DEMO", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "path",
    [
        "/api/runs",
        "/api/runs/00000000-0000-0000-0000-000000000001"
        "/approvals/00000000-0000-0000-0000-000000000002",
        "/api/products/NOVA-HOME-001/market/snapshots",
        "/api/products/NOVA-HOME-001/reviews",
    ],
)
def test_demo_rejects_mutations_before_request_validation(
    demo_mode: None, path: str
) -> None:
    response = client.post(path, json={})

    assert response.status_code == 403
    assert response.json() == {"detail": "This public demo is read-only."}


def test_demo_reports_read_only_and_keeps_get_routes_available(
    demo_mode: None,
) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json() == {"read_only_demo": True}
    assert client.get("/health").status_code == 200
