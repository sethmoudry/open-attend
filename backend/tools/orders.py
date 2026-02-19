"""Order, referral, and follow-up extraction."""

import logging

import httpx

from llm import call_medgemma_json
from models import FollowUpItem, FollowUpType
from agents import ORDER_EXTRACTION_PROMPT, FOLLOWUP_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


async def extract_orders(chunk_text: str) -> list[dict]:
    """Extract orders, referrals, and follow-up actions from text."""
    prompt = ORDER_EXTRACTION_PROMPT.format(text=chunk_text)
    result = await call_medgemma_json(prompt)

    orders: list[dict] = []
    for entry in result.get("orders", []):
        details = entry.get("details", "")
        if not details:
            continue
        orders.append(
            {
                "type": entry.get("type", "other"),
                "details": details,
                "urgency": entry.get("urgency", "routine"),
            }
        )
    return orders


async def extract_follow_ups(
    plan: str, transcript_text: str = ""
) -> list[FollowUpItem]:
    """Extract follow-up items from plan and transcript."""
    if not plan and not transcript_text:
        return []

    prompt = FOLLOWUP_EXTRACTION_PROMPT.format(
        plan=plan or "None",
        transcript=transcript_text or "None",
    )
    try:
        result = await call_medgemma_json(prompt)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Follow-up extraction failed")
        return []

    items: list[FollowUpItem] = []
    for entry in result.get("follow_ups", []):
        action = entry.get("action", "")
        if not action:
            continue
        raw_type = entry.get("type", "other").lower()
        try:
            fu_type = FollowUpType(raw_type)
        except ValueError:
            fu_type = FollowUpType.OTHER
        items.append(
            FollowUpItem(
                action=action,
                type=fu_type,
                timeframe=entry.get("timeframe"),
                details=entry.get("details"),
            )
        )
    return items
