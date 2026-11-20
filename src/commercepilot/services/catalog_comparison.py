from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from commercepilot.db.models import CatalogDraftRecord, Product
from commercepilot.models.catalog import CatalogComparison, CatalogFieldDiff

CATALOG_FIELDS: tuple[
    tuple[str, str, str],
    ...,
] = (
    ("seo_title", "SEO title", "seo_title"),
    ("meta_description", "Meta description", "meta_description"),
    ("product_description", "Product description", "description"),
    ("feature_bullets", "Feature bullets", "feature_bullets"),
    ("seo_keywords", "SEO keywords", "seo_keywords"),
    ("target_audience", "Target audience", "target_audience"),
)


def _current_value(product: Product, product_field: str) -> Any:
    value = getattr(product, product_field)
    if product_field == "seo_title" and value is None:
        return product.name
    return value


def build_catalog_comparison(
    session: Session,
    draft_id: UUID,
) -> CatalogComparison:
    draft = session.get(CatalogDraftRecord, draft_id)
    if draft is None:
        raise ValueError(f"Unknown catalog draft: {draft_id}")

    product = session.get(Product, draft.product_id)
    if product is None:
        raise ValueError(f"Catalog draft product not found: {draft.product_id}")

    fields: list[CatalogFieldDiff] = []
    for draft_field, label, product_field in CATALOG_FIELDS:
        current_value = _current_value(product, product_field)
        proposed_value = getattr(draft, draft_field)
        fields.append(
            CatalogFieldDiff(
                field=draft_field,
                label=label,
                current_value=current_value,
                proposed_value=proposed_value,
                changed=current_value != proposed_value,
            )
        )

    return CatalogComparison(
        draft_id=draft.id,
        product_id=product.id,
        product_sku=product.sku,
        status=draft.status,
        current_catalog_version=product.catalog_version,
        expected_catalog_version=draft.expected_catalog_version,
        is_stale=(
            product.catalog_version != draft.expected_catalog_version
        ),
        fields=fields,
    )
