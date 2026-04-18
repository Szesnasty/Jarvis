"""Built-in `jarvis_continue` tool — paginate truncated results."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.budget import cont_get


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="jarvis_continue",
        description=(
            "Fetch the next page of a previously truncated tool result. "
            "Pass the `continuation_token` returned by an earlier call."
        ),
    )
    async def jarvis_continue(continuation_token: str) -> dict:
        payload = cont_get(continuation_token)
        if payload is None:
            return {"error": "Continuation token expired or invalid"}
        return payload
