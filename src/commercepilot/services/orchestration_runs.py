from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from commercepilot.db.models import OrchestrationRun, Product
from commercepilot.models.enums import OrchestrationRunStatus, ProductStatus
from commercepilot.models.orchestration_api import OrchestrationRunCreate

ACTIVE_RUN_STATUSES = (
    OrchestrationRunStatus.PENDING,
    OrchestrationRunStatus.RUNNING,
    OrchestrationRunStatus.AWAITING_APPROVAL,
)


class ProductNotFoundError(ValueError):
    pass


class OrchestrationRunNotFoundError(ValueError):
    pass


class ActiveOrchestrationRunError(ValueError):
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        super().__init__(f"Product already has an active run: {run_id}")


def create_orchestration_run(
    session: Session,
    request: OrchestrationRunCreate,
) -> OrchestrationRun:
    product = session.scalar(
        select(Product).where(
            Product.sku == request.product_sku,
            Product.status == ProductStatus.ACTIVE,
        )
    )
    if product is None:
        raise ProductNotFoundError(f"Active product not found: {request.product_sku}")

    active_run = session.scalar(
        select(OrchestrationRun).where(
            OrchestrationRun.product_id == product.id,
            OrchestrationRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    if active_run is not None:
        raise ActiveOrchestrationRunError(active_run.id)

    run = OrchestrationRun(
        product=product,
        status=OrchestrationRunStatus.PENDING,
        force_catalog_update=request.force_catalog_update,
        force_campaign_update=request.force_campaign_update,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_orchestration_run(
    session: Session,
    run_id: UUID,
) -> OrchestrationRun:
    run = session.scalar(
        select(OrchestrationRun)
        .options(joinedload(OrchestrationRun.product))
        .where(OrchestrationRun.id == run_id)
    )
    if run is None:
        raise OrchestrationRunNotFoundError(f"Orchestration run not found: {run_id}")
    return run
