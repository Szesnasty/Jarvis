"""Tests for LLMService — multi-provider LLM via LiteLLM."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.claude import StreamEvent
from services.llm_service import (
    DEFAULT_MODELS,
    LLMConfig,
    LLMService,
    PROVIDER_MODEL_MAP,
    _LiteLLMToolAccumulator,
    convert_messages_for_litellm,
    convert_tools_anthropic_to_openai,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ── Model resolution ─────────────────────────────────────────────────────────


def test_resolve_model_anthropic():
    config = LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key="k")
    svc = LLMService(config)
    assert svc._litellm_model == "claude-sonnet-4-20250514"


def test_resolve_model_openai():
    config = LLMConfig(provider="openai", model="gpt-4o", api_key="k")
    svc = LLMService(config)
    assert svc._litellm_model == "gpt-4o"


def test_resolve_model_google():
    config = LLMConfig(provider="google", model="gemini-2.5-flash", api_key="k")
    svc = LLMService(config)
    assert svc._litellm_model == "gemini/gemini-2.5-flash"


def test_resolve_model_unknown_provider():
    config = LLMConfig(provider="unknown", model="some-model", api_key="k")
    svc = LLMService(config)
    # Unknown provider gets no prefix
    assert svc._litellm_model == "some-model"


# ── Tool format conversion ───────────────────────────────────────────────────


def test_convert_tools_anthropic_to_openai():
    anthropic_tools = [
        {
            "name": "search_notes",
            "description": "Search user notes",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    ]
    result = convert_tools_anthropic_to_openai(anthropic_tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "search_notes"
    assert result[0]["function"]["description"] == "Search user notes"
    assert result[0]["function"]["parameters"]["type"] == "object"


def test_convert_tools_empty():
    assert convert_tools_anthropic_to_openai([]) == []


def test_convert_tools_missing_fields():
    """Tool with no description or input_schema should still convert."""
    tools = [{"name": "simple_tool"}]
    result = convert_tools_anthropic_to_openai(tools)
    assert result[0]["function"]["name"] == "simple_tool"
    assert result[0]["function"]["description"] == ""
    assert result[0]["function"]["parameters"] == {}


# ── Message conversion ───────────────────────────────────────────────────────


def test_convert_plain_text_messages():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    result = convert_messages_for_litellm(messages)
    assert result == messages


def test_convert_tool_use_blocks():
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "search_notes",
                    "input": {"query": "test"},
                }
            ],
        },
    ]
    result = convert_messages_for_litellm(messages)
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] is None
    assert len(result[0]["tool_calls"]) == 1
    tc = result[0]["tool_calls"][0]
    assert tc["id"] == "tool_1"
    assert tc["function"]["name"] == "search_notes"
    assert json.loads(tc["function"]["arguments"]) == {"query": "test"}


def test_convert_tool_result_blocks():
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_1",
                    "content": "found 3 notes",
                }
            ],
        },
    ]
    result = convert_messages_for_litellm(messages)
    assert len(result) == 1
    assert result[0]["role"] == "tool"
    assert result[0]["tool_call_id"] == "tool_1"
    assert result[0]["content"] == "found 3 notes"


def test_convert_mixed_tool_use_and_text():
    """Assistant message with both text and tool_use blocks."""
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me search"},
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "search_notes",
                    "input": {"query": "test"},
                },
            ],
        },
    ]
    result = convert_messages_for_litellm(messages)
    assert result[0]["content"] == "Let me search"
    assert len(result[0]["tool_calls"]) == 1


# ── Tool accumulator ─────────────────────────────────────────────────────────


def _make_tc_delta(index=0, tc_id=None, name=None, arguments=None):
    """Create a mock tool call delta matching OpenAI streaming format."""
    tc = SimpleNamespace(index=index, id=tc_id, function=None)
    if name or arguments:
        tc.function = SimpleNamespace(name=name, arguments=arguments)
    return tc


def test_tool_accumulator_single_call():
    acc = _LiteLLMToolAccumulator()
    acc.process_delta([_make_tc_delta(0, tc_id="call_1", name="search_notes")])
    acc.process_delta([_make_tc_delta(0, arguments='{"query":')])
    acc.process_delta([_make_tc_delta(0, arguments=' "test"}')])
    assert acc.has_calls()

    events = acc.finish_all()
    assert len(events) == 1
    assert events[0].type == "tool_use"
    assert events[0].name == "search_notes"
    assert events[0].tool_input == {"query": "test"}
    assert events[0].tool_use_id == "call_1"
    assert not acc.has_calls()


def test_tool_accumulator_multiple_calls():
    acc = _LiteLLMToolAccumulator()
    acc.process_delta([_make_tc_delta(0, tc_id="call_1", name="search_notes")])
    acc.process_delta([_make_tc_delta(0, arguments='{"query": "a"}')])
    acc.process_delta([_make_tc_delta(1, tc_id="call_2", name="open_note")])
    acc.process_delta([_make_tc_delta(1, arguments='{"path": "test.md"}')])

    events = acc.finish_all()
    assert len(events) == 2
    assert events[0].name == "search_notes"
    assert events[1].name == "open_note"


def test_tool_accumulator_invalid_json():
    acc = _LiteLLMToolAccumulator()
    acc.process_delta([_make_tc_delta(0, tc_id="call_1", name="test")])
    acc.process_delta([_make_tc_delta(0, arguments="not json")])

    events = acc.finish_all()
    assert events[0].tool_input == {}


def test_tool_accumulator_empty():
    acc = _LiteLLMToolAccumulator()
    assert not acc.has_calls()
    assert acc.finish_all() == []


# ── LLMService streaming ────────────────────────────────────────────────────


def _make_chunk(content=None, tool_calls=None, finish_reason=None, usage=None):
    """Create a mock LiteLLM streaming chunk."""
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    chunk = SimpleNamespace(choices=[choice], usage=usage)
    return chunk


def _make_usage_chunk(prompt_tokens=100, completion_tokens=50):
    """Create a final usage-only chunk (no choices)."""
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[], usage=usage)


async def _collect_events(service, messages=None, system_prompt="", tools=None):
    """Run stream_response and collect all events."""
    events = []
    async for event in service.stream_response(
        messages=messages or [{"role": "user", "content": "hi"}],
        system_prompt=system_prompt,
        tools=tools or [],
    ):
        events.append(event)
    return events


@pytest.mark.anyio
async def test_stream_text_response():
    config = LLMConfig(provider="openai", model="gpt-4o", api_key="sk-test")
    svc = LLMService(config)

    async def fake_response(*args, **kwargs):
        chunks = [
            _make_chunk(content="Hello "),
            _make_chunk(content="world"),
            _make_chunk(finish_reason="stop"),
            _make_usage_chunk(100, 20),
        ]
        for c in chunks:
            yield c

    with patch("services.llm_service.litellm.acompletion", return_value=fake_response()):
        events = await _collect_events(svc)

    text_events = [e for e in events if e.type == "text_delta"]
    assert len(text_events) == 2
    assert text_events[0].content == "Hello "
    assert text_events[1].content == "world"

    usage_events = [e for e in events if e.type == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0].input_tokens == 100
    assert usage_events[0].output_tokens == 20

    done_events = [e for e in events if e.type == "done"]
    assert len(done_events) == 1


@pytest.mark.anyio
async def test_stream_tool_call():
    config = LLMConfig(provider="openai", model="gpt-4o", api_key="sk-test")
    svc = LLMService(config)

    tc_delta1 = _make_tc_delta(0, tc_id="call_1", name="search_notes")
    tc_delta2 = _make_tc_delta(0, arguments='{"query": "test"}')

    async def fake_response(*args, **kwargs):
        chunks = [
            _make_chunk(tool_calls=[tc_delta1]),
            _make_chunk(tool_calls=[tc_delta2]),
            _make_chunk(finish_reason="tool_calls"),
        ]
        for c in chunks:
            yield c

    with patch("services.llm_service.litellm.acompletion", return_value=fake_response()):
        events = await _collect_events(svc, tools=[{"name": "search_notes", "description": "", "input_schema": {}}])

    tool_events = [e for e in events if e.type == "tool_use"]
    assert len(tool_events) == 1
    assert tool_events[0].name == "search_notes"
    assert tool_events[0].tool_input == {"query": "test"}
    assert tool_events[0].tool_use_id == "call_1"


@pytest.mark.anyio
async def test_stream_auth_error():
    import litellm as litellm_mod

    config = LLMConfig(provider="openai", model="gpt-4o", api_key="bad-key")
    svc = LLMService(config)

    with patch("services.llm_service.litellm.acompletion", side_effect=litellm_mod.AuthenticationError(
        message="Invalid key", model="gpt-4o", llm_provider="openai",
    )):
        events = await _collect_events(svc)

    error_events = [e for e in events if e.type == "error"]
    assert len(error_events) == 1
    assert "Invalid API key" in error_events[0].content


@pytest.mark.anyio
async def test_stream_rate_limit_error():
    import litellm as litellm_mod

    config = LLMConfig(provider="openai", model="gpt-4o", api_key="sk-test")
    svc = LLMService(config)

    with patch("services.llm_service.litellm.acompletion", side_effect=litellm_mod.RateLimitError(
        message="Rate limited", model="gpt-4o", llm_provider="openai",
    )):
        events = await _collect_events(svc)

    error_events = [e for e in events if e.type == "error"]
    assert len(error_events) == 1
    assert "Rate limited" in error_events[0].content


@pytest.mark.anyio
async def test_stream_not_found_error():
    import litellm as litellm_mod

    config = LLMConfig(provider="openai", model="nonexistent", api_key="sk-test")
    svc = LLMService(config)

    with patch("services.llm_service.litellm.acompletion", side_effect=litellm_mod.NotFoundError(
        message="Not found", model="nonexistent", llm_provider="openai",
    )):
        events = await _collect_events(svc)

    error_events = [e for e in events if e.type == "error"]
    assert len(error_events) == 1
    assert "Model not available" in error_events[0].content


@pytest.mark.anyio
async def test_stream_passes_correct_kwargs():
    config = LLMConfig(provider="google", model="gemini-2.5-flash", api_key="goog-key", max_tokens=2048)
    svc = LLMService(config)

    captured_kwargs = {}

    async def capture_kwargs(**kwargs):
        captured_kwargs.update(kwargs)
        return
        yield  # make it an async generator  # noqa: E275

    with patch("services.llm_service.litellm.acompletion", side_effect=capture_kwargs):
        events = await _collect_events(svc, system_prompt="You are Jarvis")

    assert captured_kwargs["model"] == "gemini/gemini-2.5-flash"
    assert captured_kwargs["api_key"] == "goog-key"
    assert captured_kwargs["max_tokens"] == 2048
    assert captured_kwargs["stream"] is True
    # System prompt should be first message
    assert captured_kwargs["messages"][0]["role"] == "system"
    assert captured_kwargs["messages"][0]["content"] == "You are Jarvis"


@pytest.mark.anyio
async def test_stream_converts_tools_in_kwargs():
    config = LLMConfig(provider="openai", model="gpt-4o", api_key="sk-test")
    svc = LLMService(config)

    captured_kwargs = {}

    async def capture_kwargs(**kwargs):
        captured_kwargs.update(kwargs)
        return
        yield  # noqa: E275

    anthropic_tools = [
        {"name": "search_notes", "description": "Search", "input_schema": {"type": "object"}},
    ]

    with patch("services.llm_service.litellm.acompletion", side_effect=capture_kwargs):
        await _collect_events(svc, tools=anthropic_tools)

    assert captured_kwargs["tools"][0]["type"] == "function"
    assert captured_kwargs["tools"][0]["function"]["name"] == "search_notes"


@pytest.mark.anyio
async def test_close_is_noop():
    config = LLMConfig(provider="openai", model="gpt-4o", api_key="k")
    svc = LLMService(config)
    await svc.close()  # should not raise


# ── Default models and provider map ──────────────────────────────────────────


def test_default_models_has_all_providers():
    assert "anthropic" in DEFAULT_MODELS
    assert "openai" in DEFAULT_MODELS
    assert "google" in DEFAULT_MODELS


def test_provider_model_map_google_prefix():
    assert PROVIDER_MODEL_MAP["google"] == "gemini/"
    assert PROVIDER_MODEL_MAP["anthropic"] == ""
    assert PROVIDER_MODEL_MAP["openai"] == ""
