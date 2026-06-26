from __future__ import annotations

from pathlib import Path

from .extractors import TextExtractor
from .llm import LLMParseError, OpenAICompatibleClient
from .models import ParseResult
from .parser import ResumeParser


class ResumeParseAgent:
    def __init__(
        self,
        extractor: TextExtractor | None = None,
        parser: ResumeParser | None = None,
        llm_client: OpenAICompatibleClient | None = None,
        use_llm: bool | None = None,
        fallback_to_rules: bool = True,
    ) -> None:
        self.extractor = extractor or TextExtractor()
        self.parser = parser or ResumeParser()
        self.llm_client = llm_client or OpenAICompatibleClient()
        self.use_llm = self.llm_client.is_configured if use_llm is None else use_llm
        self.fallback_to_rules = fallback_to_rules

    def parse(self, file_path: str | Path) -> ParseResult:
        text, warnings = self.extractor.extract(file_path)
        if self.use_llm:
            try:
                result = self.llm_client.parse_resume(text)
                result.warnings.extend(warnings)
                return result
            except LLMParseError as exc:
                if not self.fallback_to_rules:
                    raise
                warnings.append(f"LLM parsing failed, used rule parser instead: {exc}")

        return self.parser.parse(text, warnings=warnings)
