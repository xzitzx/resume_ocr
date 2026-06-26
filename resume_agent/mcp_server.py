from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .agent import ResumeParseAgent
from .extractors import TextExtractionError, TextExtractor
from .llm import LLMParseError, OpenAICompatibleClient


mcp = FastMCP("resume-parse-agent")


@mcp.tool()
def parse_resume_file(
    file_path: str,
    use_llm: bool = True,
    fallback_to_rules: bool = False,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Parse a local resume file into structured JSON.

    Supports txt, md, pdf, docx, and common image formats when the optional
    parser dependencies are installed. LLM credentials are read from
    LLM_API_KEY or OPENAI_API_KEY.
    """
    path = _resolve_file_path(file_path)
    client = OpenAICompatibleClient(base_url=base_url, model=model)
    agent = ResumeParseAgent(
        llm_client=client,
        use_llm=use_llm,
        fallback_to_rules=fallback_to_rules,
    )

    try:
        return agent.parse(path).to_dict()
    except (FileNotFoundError, TextExtractionError, LLMParseError) as exc:
        return {"error": str(exc), "file_path": str(path)}


@mcp.tool()
def extract_resume_text(file_path: str) -> dict[str, Any]:
    """Extract raw text from a local resume file without LLM parsing."""
    path = _resolve_file_path(file_path)
    extractor = TextExtractor()

    try:
        text, warnings = extractor.extract(path)
        return {
            "file_path": str(path),
            "text": text,
            "warnings": warnings,
        }
    except (FileNotFoundError, TextExtractionError) as exc:
        return {"error": str(exc), "file_path": str(path)}


def _resolve_file_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
