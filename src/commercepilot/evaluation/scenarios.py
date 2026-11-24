from commercepilot.evaluation.models import EvaluationCase, EvaluationTarget
from commercepilot.graph.orchestrator_graph import (
    APPLY_APPROVAL_POLICY_NODE,
    RUN_CAMPAIGN_AGENT_NODE,
    RUN_CATALOG_AGENT_NODE,
)
from commercepilot.models.enums import ActionType, CampaignChannel

SAFE_STRATEGY_ROUTES = [
    RUN_CATALOG_AGENT_NODE,
    RUN_CAMPAIGN_AGENT_NODE,
    APPLY_APPROVAL_POLICY_NODE,
]
FORBIDDEN_STRATEGY_ACTIONS = [
    ActionType.PUBLISH_CATALOG_UPDATE,
    ActionType.LAUNCH_CAMPAIGN,
]

EVALUATION_CASES = (
    EvaluationCase(
        id="review-novafit-core-themes",
        name="NovaFit review analysis identifies recurring strengths and complaints",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-WEAR-001",
        required_topic_groups=[
            ["battery", "charge"],
            ["gps", "location", "distance"],
            ["sleep", "wake"],
        ],
    ),
    EvaluationCase(
        id="review-novabrew-core-themes",
        name="NovaBrew review analysis identifies espresso and usability themes",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-HOME-001",
        required_topic_groups=[
            ["espresso", "crema", "shot"],
            ["steam", "milk", "froth"],
            ["drip", "tray", "clean"],
        ],
    ),
    EvaluationCase(
        id="competitor-novafit-price-pressure",
        name="NovaFit competitor analysis recognizes promotional price pressure",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-WEAR-001",
        expected_competitors=["PulseLabs", "Kinetic", "WellSync"],
        expected_price_drop_competitors=["PulseLabs", "WellSync"],
    ),
    EvaluationCase(
        id="competitor-novabrew-price-pressure",
        name="NovaBrew competitor analysis recognizes the MorningPro discount",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-HOME-001",
        expected_competitors=["BrewCraft", "CafeWorks", "BeanForge"],
        expected_price_drop_competitors=["BeanForge"],
    ),
    EvaluationCase(
        id="governance-catalog-and-price",
        name="Catalog routing precedes deterministic approval for a price mutation",
        target=EvaluationTarget.GOVERNANCE,
        product_sku="NOVA-WEAR-001",
        proposed_action_types=[
            ActionType.DRAFT_CATALOG_UPDATE,
            ActionType.CHANGE_PRICE,
            ActionType.MONITOR_COMPETITORS,
        ],
        expected_route=RUN_CATALOG_AGENT_NODE,
        expected_human_approval=True,
    ),
    EvaluationCase(
        id="review-novasound-strengths",
        name="NovaSound review analysis captures established product strengths",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-AUDIO-001",
        required_topic_groups=[
            ["sound", "audio"],
            ["battery", "charge"],
            ["noise cancellation", "anc"],
        ],
    ),
    EvaluationCase(
        id="review-novasound-complaints",
        name="NovaSound review analysis captures recurring customer complaints",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-AUDIO-001",
        required_topic_groups=[
            ["microphone", "call"],
            ["bluetooth", "connection", "disconnect"],
            ["comfort", "tight", "pressure"],
        ],
    ),
    EvaluationCase(
        id="review-novafit-ux-issues",
        name="NovaFit review analysis captures wearable usability issues",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-WEAR-001",
        required_topic_groups=[
            ["strap", "skin", "irrit"],
            ["notification", "message", "late"],
            ["app", "phone", "tap"],
        ],
    ),
    EvaluationCase(
        id="review-novabrew-operational-issues",
        name="NovaBrew review analysis captures maintenance and workflow issues",
        target=EvaluationTarget.REVIEW_AGENT,
        product_sku="NOVA-HOME-001",
        required_topic_groups=[
            ["clean", "descal", "manual"],
            ["tank", "refill", "cabinet"],
            ["drip", "water", "mess"],
        ],
    ),
    EvaluationCase(
        id="competitor-novasound-landscape",
        name="NovaSound competitor analysis covers the complete market set",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-AUDIO-001",
        expected_competitors=["AudioPeak", "SonicForge", "ClearWave"],
    ),
    EvaluationCase(
        id="competitor-novasound-grounding",
        name="NovaSound competitor findings remain grounded in price snapshots",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-AUDIO-001",
        expected_competitors=["AudioPeak", "SonicForge", "ClearWave"],
    ),
    EvaluationCase(
        id="competitor-novafit-grounding",
        name="NovaFit competitor findings cite the complete evidence set",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-WEAR-001",
        expected_competitors=["PulseLabs", "Kinetic", "WellSync"],
    ),
    EvaluationCase(
        id="competitor-novabrew-grounding",
        name="NovaBrew competitor findings cite the complete evidence set",
        target=EvaluationTarget.COMPETITOR_AGENT,
        product_sku="NOVA-HOME-001",
        expected_competitors=["BrewCraft", "CafeWorks", "BeanForge"],
    ),
    *(
        EvaluationCase(
            id=f"strategy-{slug}-grounding",
            name=f"{name} strategy uses grounded evidence and valid routing",
            target=EvaluationTarget.STRATEGY,
            product_sku=sku,
            minimum_action_count=1,
            forbidden_action_types=FORBIDDEN_STRATEGY_ACTIONS,
            allowed_routes=SAFE_STRATEGY_ROUTES,
        )
        for slug, name, sku in (
            ("novasound", "NovaSound", "NOVA-AUDIO-001"),
            ("novafit", "NovaFit", "NOVA-WEAR-001"),
            ("novabrew", "NovaBrew", "NOVA-HOME-001"),
        )
    ),
    *(
        EvaluationCase(
            id=f"strategy-{slug}-action-safety",
            name=f"{name} strategy avoids unsupported executable actions",
            target=EvaluationTarget.STRATEGY,
            product_sku=sku,
            minimum_action_count=1,
            forbidden_action_types=FORBIDDEN_STRATEGY_ACTIONS,
            allowed_routes=SAFE_STRATEGY_ROUTES,
        )
        for slug, name, sku in (
            ("novasound", "NovaSound", "NOVA-AUDIO-001"),
            ("novafit", "NovaFit", "NOVA-WEAR-001"),
            ("novabrew", "NovaBrew", "NOVA-HOME-001"),
        )
    ),
    EvaluationCase(
        id="catalog-novasound-grounding",
        name="NovaSound catalog copy remains grounded in product evidence",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-AUDIO-001",
        required_topic_groups=[["NovaSound Pro"], ["battery", "30"]],
    ),
    EvaluationCase(
        id="catalog-novasound-positioning",
        name="NovaSound catalog copy communicates supported positioning",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-AUDIO-001",
        required_topic_groups=[["audio", "sound"], ["noise", "ANC"]],
    ),
    EvaluationCase(
        id="catalog-novafit-grounding",
        name="NovaFit catalog copy remains grounded in product evidence",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-WEAR-001",
        required_topic_groups=[["NovaFit Watch"], ["battery", "seven", "7"]],
    ),
    EvaluationCase(
        id="catalog-novafit-positioning",
        name="NovaFit catalog copy communicates supported wearable capabilities",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-WEAR-001",
        required_topic_groups=[["GPS"], ["heart", "health"], ["AMOLED", "display"]],
    ),
    EvaluationCase(
        id="catalog-novabrew-grounding",
        name="NovaBrew catalog copy remains grounded in product evidence",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-HOME-001",
        required_topic_groups=[["NovaBrew Pro"], ["15", "bar"]],
    ),
    EvaluationCase(
        id="catalog-novabrew-positioning",
        name="NovaBrew catalog copy communicates supported brewing capabilities",
        target=EvaluationTarget.CATALOG_AGENT,
        product_sku="NOVA-HOME-001",
        required_topic_groups=[
            ["espresso"],
            ["thermoblock", "heat"],
            ["steam", "milk"],
        ],
    ),
    EvaluationCase(
        id="campaign-novasound-channel-coverage",
        name="NovaSound campaign produces one asset for every supported channel",
        target=EvaluationTarget.CAMPAIGN_AGENT,
        product_sku="NOVA-AUDIO-001",
        expected_channels=[
            CampaignChannel.EMAIL,
            CampaignChannel.SOCIAL,
            CampaignChannel.PAID_SEARCH,
        ],
    ),
    EvaluationCase(
        id="campaign-novasound-grounding",
        name="NovaSound campaign remains grounded in published catalog evidence",
        target=EvaluationTarget.CAMPAIGN_AGENT,
        product_sku="NOVA-AUDIO-001",
        required_topic_groups=[
            ["audio", "sound", "listen"],
            ["battery", "30"],
            ["noise", "ANC"],
        ],
    ),
    EvaluationCase(
        id="governance-campaign-draft",
        name="Campaign draft routes to its agent without premature approval",
        target=EvaluationTarget.GOVERNANCE,
        product_sku="NOVA-AUDIO-001",
        proposed_action_types=[ActionType.DRAFT_CAMPAIGN],
        expected_route=RUN_CAMPAIGN_AGENT_NODE,
        expected_human_approval=False,
    ),
    EvaluationCase(
        id="governance-monitoring-only",
        name="Read-only monitoring bypasses human approval",
        target=EvaluationTarget.GOVERNANCE,
        product_sku="NOVA-WEAR-001",
        proposed_action_types=[ActionType.MONITOR_COMPETITORS],
        expected_route=APPLY_APPROVAL_POLICY_NODE,
        expected_human_approval=False,
    ),
    EvaluationCase(
        id="governance-price-change",
        name="Price mutation always requires human approval",
        target=EvaluationTarget.GOVERNANCE,
        product_sku="NOVA-HOME-001",
        proposed_action_types=[ActionType.CHANGE_PRICE],
        expected_route=APPLY_APPROVAL_POLICY_NODE,
        expected_human_approval=True,
    ),
)

INITIAL_EVALUATION_CASES = EVALUATION_CASES[:5]
