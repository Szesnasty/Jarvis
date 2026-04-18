"""Jarvis MCP server — modular, FastMCP-based, stdio-only.

Standalone CLI that exposes Jarvis knowledge bases (notes, graph, jira,
sessions, preferences) as MCP tools to clients like Cursor, Claude Desktop,
VS Code, Continue, Zed.

This package is independent of the FastAPI backend (`main.py`, `routers/`).
It depends on `services/*` for business logic only.
"""
