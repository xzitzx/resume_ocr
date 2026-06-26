from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import ResumeParseAgent
from .llm import LLMParseError, OpenAICompatibleClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a resume file into structured JSON.")
    parser.add_argument("resume", help="Path to a resume file.")
    parser.add_argument("-o", "--output", help="Write JSON result to this file.")
    parser.add_argument("--ensure-ascii", action="store_true", help="Escape non-ASCII characters in JSON.")
    parser.add_argument("--llm", action="store_true", help="Use a configured LLM provider.")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM parsing and use local rules only.")
    parser.add_argument("--model", help="LLM model name. Defaults to LLM_MODEL or gpt-4o-mini.")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL. Defaults to LLM_BASE_URL or OpenAI.")
    parser.add_argument("--strict-llm", action="store_true", help="Fail instead of falling back to rules when LLM parsing fails.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    use_llm = True if args.llm else None
    if args.no_llm:
        use_llm = False
    client = OpenAICompatibleClient(base_url=args.base_url, model=args.model)
    agent = ResumeParseAgent(
        llm_client=client,
        use_llm=use_llm,
        fallback_to_rules=not args.strict_llm,
    )
    try:
        result = agent.parse(args.resume)
    except LLMParseError as exc:
        print(f"LLM parsing failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    payload = json.dumps(result.to_dict(), ensure_ascii=args.ensure_ascii, indent=2)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        return
    print(payload)


if __name__ == "__main__":
    main()
