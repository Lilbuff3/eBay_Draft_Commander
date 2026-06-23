"""Tests for robust JSON extraction from Gemini model responses.

The live failure: Gemini sometimes returns two JSON objects (or one object plus
trailing data). The old greedy `(\\{.*\\})` regex spanned the first `{` to the last
`}`, so `json.loads` parsed object 1 and then choked on object 2 with
`Extra data: line N column 1`. `_extract_json_object` must parse the FIRST complete
JSON object and ignore anything after it.
"""
from backend.app.services.ai_analyzer import _extract_json_object


def test_clean_single_object():
    assert _extract_json_object('{"a": 1, "b": "two"}') == {"a": 1, "b": "two"}


def test_object_with_trailing_second_object():
    # The exact live "Extra data" case: a valid object followed by another object.
    text = '{"identification": {"brand": "Sony"}}\n{"junk": true}'
    assert _extract_json_object(text) == {"identification": {"brand": "Sony"}}


def test_object_with_trailing_prose():
    text = '{"price": 38.99}\n\nHere is the listing you asked for.'
    assert _extract_json_object(text) == {"price": 38.99}


def test_markdown_fenced_object():
    text = '```json\n{"title": "Widget"}\n```'
    assert _extract_json_object(text) == {"title": "Widget"}


def test_bare_fence_without_lang():
    text = '```\n{"title": "Widget"}\n```'
    assert _extract_json_object(text) == {"title": "Widget"}


def test_leading_prose_then_object():
    text = 'Sure, here is the JSON:\n{"ok": 1}'
    assert _extract_json_object(text) == {"ok": 1}


def test_nested_braces_parse_whole_object():
    text = '{"outer": {"inner": {"deep": [1, 2, 3]}}, "tail": 9}'
    assert _extract_json_object(text) == {"outer": {"inner": {"deep": [1, 2, 3]}}, "tail": 9}


def test_top_level_array_takes_first_dict():
    text = '[{"first": 1}, {"second": 2}]'
    assert _extract_json_object(text) == {"first": 1}


def test_no_json_returns_none():
    assert _extract_json_object("no json here at all") is None


def test_empty_string_returns_none():
    assert _extract_json_object("") is None


def test_garbage_after_brace_returns_none():
    # A '{' that does not begin a valid JSON object should not raise.
    assert _extract_json_object("{ this is not json") is None


def test_none_input_returns_none():
    assert _extract_json_object(None) is None
