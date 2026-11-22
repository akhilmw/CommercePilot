from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import OrchestrationRun, Product
from commercepilot.models.enums import OrchestrationRunStatus, ProductStatus
from commercepilot.models.orchestration_api import OrchestrationRunCreate
from commercepilot.services.orchestration_runs import (
    ActiveOrchestrationRunError,
    OrchestrationRunNotFoundError,
    ProductNotFoundError,
    create_orchestration_run,
    get_orchestration_run,
)


def make_product() -> Product:
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless over-ear headphones.",
        price=99.99,
        currency="USD",
        status=ProductStatus.ACTIVE,
    )


def test_create_run_persists_selected_product_and_flags() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.side_effect = [product, None]
    request = OrchestrationRunCreate(
        product_sku=product.sku,
        force_campaign_update=True,
    )

    run = create_orchestration_run(session, request)

    assert run.product is product
    assert run.status is OrchestrationRunStatus.PENDING
    assert run.force_catalog_update is False
    assert run.force_campaign_update is True
    session.add.assert_called_once_with(run)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(run)


def test_create_run_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ProductNotFoundError, match="NOVA-MISSING-001"):
        create_orchestration_run(
            session,
            OrchestrationRunCreate(product_sku="NOVA-MISSING-001"),
        )

    session.add.assert_not_called()


def test_create_run_rejects_second_active_run_for_product() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    active_run = OrchestrationRun(
        id=uuid4(),
        product=product,
        status=OrchestrationRunStatus.AWAITING_APPROVAL,
    )
    session.scalar.side_effect = [product, active_run]

    with pytest.raises(ActiveOrchestrationRunError) as error:
        create_orchestration_run(
            session,
            OrchestrationRunCreate(product_sku=product.sku),
        )

    assert error.value.run_id == active_run.id
    session.add.assert_not_called()


def test_get_run_rejects_unknown_id() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    run_id = uuid4()

    with pytest.raises(OrchestrationRunNotFoundError, match=str(run_id)):
        get_orchestration_run(session, run_id)
