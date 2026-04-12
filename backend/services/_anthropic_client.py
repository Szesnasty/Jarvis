"""Thin wrapper around anthropic client to make it mockable."""
import anthropic


def create_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)
