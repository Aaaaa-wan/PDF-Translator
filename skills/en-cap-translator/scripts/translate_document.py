#!/usr/bin/env python3
"""Create translation worksheets and validate canonical bilingual markdown."""

from __future__ import annotations

import argparse
import json
import sys

from _bilingual_markdown import build_skeleton, format_issue, read_text, validate_text, write_text


def command_skeleton(args: argparse.Namespace) -> int:
    source = read_text(args.input)
    skeleton = build_skeleton(source)
    write_text(args.output, skeleton)
    print(f"Wrote translation worksheet to {args.output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    text = read_text(args.input)
    blocks, issues = validate_text(text)
    paired_count = sum(1 for block in blocks if hasattr(block, "english"))
    single_count = len(blocks) - paired_count

    if args.json:
        payload = {
            "valid": not issues,
            "paired_blocks": paired_count,
            "single_blocks": single_count,
            "issues": [{"line": issue.line, "message": issue.message} for issue in issues],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if issues:
            print("Validation failed:")
            for issue in issues:
                print(f"- {format_issue(issue)}")
        else:
            print(
                f"Validation succeeded: {paired_count} bilingual blocks, {single_count} verbatim blocks."
            )

    return 1 if issues else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or validate canonical bilingual markdown for autonomous-driving regulations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    skeleton = subparsers.add_parser(
        "skeleton",
        help="Generate a translation worksheet with TODO_TRANSLATE placeholders.",
    )
    skeleton.add_argument("input", help="Source markdown or plain text file.")
    skeleton.add_argument("output", help="Output worksheet path.")
    skeleton.set_defaults(func=command_skeleton)

    validate = subparsers.add_parser(
        "validate",
        help="Validate canonical bilingual markdown before packaging.",
    )
    validate.add_argument("input", help="Bilingual markdown file.")
    validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    validate.set_defaults(func=command_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
