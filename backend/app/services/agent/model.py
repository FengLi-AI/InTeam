"""OpenAI-compatible HTTP adapter; no model credentials or hidden reasoning enter traces."""
import httpx
from ...core.config import settings
from .knowledge import TOOLS


async def complete(messages: list[dict], *, require_tools: bool = False) -> dict:
    key = settings.agent_api_key or settings.deepseek_api_key
    if not key:
        raise RuntimeError("model_not_configured")
    body = {
        "model": settings.agent_model, "messages": messages, "tools": TOOLS,
        "tool_choice": "required" if require_tools else "auto", "max_tokens": 5500,
        "stream": False,
    }
    if "deepseek" in settings.agent_base_url:
        body["thinking"] = {"type": "disabled"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(70, connect=10), follow_redirects=False) as client:
        response = await client.post(settings.agent_base_url + "/chat/completions", json=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        response.raise_for_status()
        data = response.json()
    choice = data["choices"][0]
    if choice.get("finish_reason") not in {"stop", "tool_calls"}:
        raise ValueError("incomplete_model_response")
    msg = choice["message"]
    # Only public assistant content and function requests are retained.
    return {k: msg[k] for k in ("role", "content", "tool_calls") if k in msg}
