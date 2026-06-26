from __future__ import annotations

from pathlib import Path

from .extractors import TextExtractor
from .llm import OpenAICompatibleClient
from .models import ParseResult
from .parser import ResumeParser
from .workflow import ResumeAgentWorkflow


class ResumeParseAgent:
    def __init__(
        self,
        extractor: TextExtractor | None = None,
        parser: ResumeParser | None = None,
        llm_client: OpenAICompatibleClient | None = None,
        use_llm: bool | None = None,
        fallback_to_rules: bool = True,
        repair_with_llm: bool = True,
    ) -> None:
        self.extractor = extractor or TextExtractor()
        self.parser = parser or ResumeParser()
        self.llm_client = llm_client or OpenAICompatibleClient()
        self.use_llm = self.llm_client.is_configured if use_llm is None else use_llm
        self.fallback_to_rules = fallback_to_rules
        self.repair_with_llm = repair_with_llm

    def parse(self, file_path: str | Path) -> ParseResult:
        workflow = ResumeAgentWorkflow(
            extractor=self.extractor,
            parser=self.parser,
            llm_client=self.llm_client,
            use_llm=self.use_llm,
            fallback_to_rules=self.fallback_to_rules,
            repair_with_llm=self.repair_with_llm,
        )
        return workflow.run(file_path)
