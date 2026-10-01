"""Test runner output parsers (dart_json, ohw_jsonl) -> common event format. Pure Python."""

from judge.parsers.dart_json import DartJsonParser

_PARSERS = {"dart_json": DartJsonParser}


def make_parser(name: str, stage: int = 1, first_index: int = 1) -> DartJsonParser:
    """The parser a runner profile names in its ``parser`` field."""
    try:
        parser_class = _PARSERS[name]
    except KeyError:
        raise ValueError(f"unknown parser {name!r}") from None
    return parser_class(stage=stage, first_index=first_index)
