# [Input] Messy LLM text that may contain prose, Markdown JSON fences,
#         Python-style tool-call arguments, or slightly malformed JSON.
# [Output] Reusable parsing helpers for extracting JSON objects/arrays.
# [Pos] backend utility module for Claude/LLM result parsing.
# [Sync] 2026-06-27: adapted from InterpretationoDreams try_parse_json_object.py
#         (MIT) with optional json_repair support and array extraction helpers.

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

try:  # Optional dependency used by the referenced InterpretationoDreams helper.
    from json_repair import repair_json as _repair_json
except Exception:  # pragma: no cover - dependency may be absent in local tests.
    _repair_json = None

log = logging.getLogger(__name__)


def try_parse_ast_to_json(function_string: str) -> tuple[str, dict[str, Any]]:
    """Parse Python-style function-call arguments into a JSON-like dict.

    This mirrors the helper from InterpretationoDreams for cases where an LLM
    emits a tool-call-shaped payload rather than strict JSON.
    """
    tree = ast.parse(str(function_string).strip())
    ast_info = ""
    json_result: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function_name = getattr(node.func, "id", "")
            args = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            ast_info += f"Function Name: {function_name}\r\n"
            for arg, value in args.items():
                ast_info += f"Argument Name: {arg}\n"
                ast_info += f"Argument Value: {ast.dump(value)}\n"
                json_result[arg] = ast.literal_eval(value)
    return ast_info, json_result


def _strip_markdown_json_frame(value: str) -> str:
    text = value.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    elif text.startswith("```"):
        text = text[len("```") :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()


def _clean_json_string(value: str) -> str:
    return (
        _strip_markdown_json_frame(value)
        .replace("{{", "{")
        .replace("}}", "}")
        .replace('"[{', "[{")
        .replace('}]"', "}]")
        .replace("\\n", " ")
        .replace("\n", " ")
        .replace("\r", "")
        .strip()
    )


def _escape_unescaped_quotes_in_strings(candidate: str) -> str:
    """Best-effort fallback when LLM text leaves inner quotes unescaped."""
    repaired: list[str] = []
    in_string = False
    escaped = False
    length = len(candidate)
    for index, char in enumerate(candidate):
        if char != '"':
            repaired.append(char)
            if in_string and char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
            continue
        if escaped:
            repaired.append(char)
            escaped = False
            continue
        if not in_string:
            in_string = True
            repaired.append(char)
            continue
        next_index = index + 1
        while next_index < length and candidate[next_index].isspace():
            next_index += 1
        next_char = candidate[next_index] if next_index < length else ""
        if next_char in {":", ",", "}", "]", ""}:
            in_string = False
            repaired.append(char)
        else:
            repaired.append('\\"')
    return "".join(repaired)


def _repair_with_json_repair(value: str) -> str | None:
    if _repair_json is None:
        return None
    try:
        return str(_repair_json(json_str=value, return_objects=False))
    except Exception:
        log.debug("json_repair failed", exc_info=True)
        return None


def _try_loads(value: str) -> Any | None:
    attempts = [value, _clean_json_string(value)]
    repaired = _repair_with_json_repair(attempts[-1])
    if repaired:
        attempts.append(repaired)
    attempts.append(_escape_unescaped_quotes_in_strings(attempts[-1]))
    for attempt in attempts:
        try:
            return json.loads(attempt)
        except Exception:
            continue
    return None


def try_parse_json_object(input: str) -> tuple[str, dict[str, Any]]:
    """Clean and parse an LLM JSON object, following InterpretationoDreams.

    Returns a tuple of the cleaned/repaired JSON text and the parsed dict. If no
    object can be parsed, the dict is empty.
    """
    result = _try_loads(input)
    if isinstance(result, dict):
        return input, result

    match = re.search(r"\{(.*)\}", input, flags=re.DOTALL)
    candidate = "{" + match.group(1) + "}" if match else input
    cleaned = _clean_json_string(candidate)
    result = _try_loads(cleaned)
    if isinstance(result, dict):
        return cleaned, result

    try:
        ast_info, ast_result = try_parse_ast_to_json(cleaned)
        if ast_result:
            return ast_info, ast_result
    except Exception:
        log.debug("AST JSON parse failed", exc_info=True)
    return cleaned, {}


def json_fence_candidates(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if match.group(1).strip()
    ]


def balanced_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for open_char, close_char in (("[", "]"), ("{", "}")):
        start = text.find(open_char)
        while start != -1:
            depth = 0
            in_string = False
            escaped = False
            for index in range(start, len(text)):
                char = text[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == open_char:
                    depth += 1
                elif char == close_char:
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start : index + 1].strip())
                        break
            start = text.find(open_char, start + 1)
    return candidates


def try_parse_json_value(input: str) -> tuple[str, Any | None]:
    """Parse any JSON value from messy LLM output."""
    cleaned = _clean_json_string(input)
    return cleaned, _try_loads(cleaned)


def try_parse_json_array(input: str) -> tuple[str, list[Any]]:
    """Extract and parse the latest valid JSON array from messy LLM output."""
    stripped = input.strip()
    balanced = balanced_json_candidates(stripped)
    candidates = (
        list(reversed(json_fence_candidates(stripped)))
        + [stripped]
        + [candidate for candidate in balanced if candidate.startswith("[")]
    )
    for candidate in candidates:
        cleaned, value = try_parse_json_value(candidate)
        if isinstance(value, list):
            return cleaned, value
    return stripped, []
