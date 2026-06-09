"""A2A delegation helper for the Day 8 runtime."""

from __future__ import annotations

import logging
from uuid import uuid4

import httpx

from a2a.client import A2AClient
from a2a.types import AgentCard, Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

logger = logging.getLogger(__name__)


async def delegate(
    endpoint: str,
    question: str,
    context_id: str,
    trace_id: str,
    depth: int,
) -> str:
    """Send a question to another A2A agent and return the text response."""
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        card_url = f"{endpoint}/.well-known/agent.json"
        card_resp = await http_client.get(card_url)
        card_resp.raise_for_status()
        agent_card = AgentCard.model_validate(card_resp.json())

        client = A2AClient(httpx_client=http_client, agent_card=agent_card)
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=question))],
            message_id=str(uuid4()),
            context_id=context_id,
            metadata={
                "trace_id": trace_id,
                "context_id": context_id,
                "delegation_depth": depth,
            },
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )
        logger.debug("Delegating to %s | trace=%s depth=%d", endpoint, trace_id, depth)
        response = await client.send_message(request)
        return _extract_text(response)


def _extract_text(response: object) -> str:
    text = ""
    if hasattr(response, "root"):
        response = response.root

    result = getattr(response, "result", None)
    if result is None:
        return text

    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            for part in getattr(artifact, "parts", []) or []:
                text += _part_text(part)
        if text:
            return text

    parts = getattr(result, "parts", None)
    if parts:
        for part in parts:
            text += _part_text(part)

    if not text:
        history = getattr(result, "history", None)
        if history:
            for message in history:
                for part in getattr(message, "parts", []) or []:
                    text += _part_text(part)
    return text


def _part_text(part: object) -> str:
    inner = getattr(part, "root", part)
    return getattr(inner, "text", "") or ""

