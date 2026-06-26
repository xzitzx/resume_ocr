from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .extractors import TextExtractor
from .llm import LLMParseError
from .models import ParseResult
from .parser import ResumeParser


class LLMClient(Protocol):
    model: str
    is_configured: bool

    def parse_resume(self, text: str) -> ParseResult:
        ...


@dataclass
class AgentContext:
    file_path: Path
    text: str = ""
    extraction_warnings: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


class ResumeAgentWorkflow:
    SECTION_HEADINGS = {
        "basic information",
        "contact",
        "profile",
        "resume",
        "personal resume",
        "基本信息",
        "个人信息",
        "联系方式",
        "简历",
        "个人简历",
    }

    def __init__(
        self,
        extractor: TextExtractor,
        parser: ResumeParser,
        llm_client: LLMClient,
        use_llm: bool,
        fallback_to_rules: bool,
        repair_with_llm: bool = True,
    ) -> None:
        self.extractor = extractor
        self.parser = parser
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.fallback_to_rules = fallback_to_rules
        self.repair_with_llm = repair_with_llm

    def run(self, file_path: str | Path) -> ParseResult:
        context = AgentContext(file_path=Path(file_path))
        context.steps.append("plan: extract text, parse, validate, repair if useful, finalize")

        context.text, context.extraction_warnings = self.extractor.extract(context.file_path)
        context.steps.append(f"extract_text: {len(context.text)} characters")

        text_issues = self._inspect_text_quality(context.text)
        if text_issues:
            context.steps.append(f"text_quality: {len(text_issues)} issue(s)")
        else:
            context.steps.append("text_quality: ok")

        result = self._parse(context)
        result.warnings.extend(context.extraction_warnings)

        issues = text_issues + self._validate_result(result, context.text)
        if issues:
            context.steps.append(f"validate_result: {len(issues)} issue(s)")
        else:
            context.steps.append("validate_result: ok")

        if self._should_repair(result, issues):
            repaired = self._repair(context, result, issues)
            if repaired is not None:
                repaired_issues = text_issues + self._validate_result(repaired, context.text)
                if self._score(repaired_issues) >= self._score(issues):
                    result = repaired
                    issues = repaired_issues
                    context.steps.append("repair: accepted")
                else:
                    context.steps.append("repair: rejected")

        result.quality_issues = issues
        result.confidence_score = self._score(issues)
        result.agent_steps = context.steps
        return result

    def _parse(self, context: AgentContext) -> ParseResult:
        if self.use_llm:
            try:
                result = self.llm_client.parse_resume(context.text)
                context.steps.append(f"parse: llm ({self.llm_client.model})")
                return result
            except LLMParseError as exc:
                context.steps.append(f"parse: llm_failed ({exc})")
                if not self.fallback_to_rules:
                    raise
                context.extraction_warnings.append(f"LLM parsing failed, used rule parser instead: {exc}")

        result = self.parser.parse(context.text)
        context.steps.append("parse: rules")
        return result

    def _repair(
        self,
        context: AgentContext,
        result: ParseResult,
        issues: list[str],
    ) -> ParseResult | None:
        repair_method = getattr(self.llm_client, "repair_resume", None)
        if repair_method is None:
            context.steps.append("repair: unavailable")
            return None

        try:
            context.steps.append("repair: llm_attempt")
            return repair_method(context.text, result, issues)
        except LLMParseError as exc:
            context.steps.append(f"repair: llm_failed ({exc})")
            result.warnings.append(f"LLM repair failed: {exc}")
            return None

    def _should_repair(self, result: ParseResult, issues: list[str]) -> bool:
        return (
            self.use_llm
            and self.repair_with_llm
            and result.parser.startswith("llm")
            and bool(issues)
        )

    def _inspect_text_quality(self, text: str) -> list[str]:
        issues: list[str] = []
        stripped = text.strip()
        if not stripped:
            return ["No text was extracted from the resume."]
        if len(stripped) < 120:
            issues.append("Extracted text is very short; PDF/OCR extraction may have failed.")

        meaningful_chars = re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]", stripped)
        ratio = len(meaningful_chars) / max(len(stripped), 1)
        if ratio < 0.35:
            issues.append("Extracted text has a low readable-character ratio; OCR quality may be poor.")

        if not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", stripped) and not re.search(r"1[3-9]\d{9}", stripped):
            issues.append("No email or mainland China mobile number was visible in extracted text.")
        return issues

    def _validate_result(self, result: ParseResult, text: str) -> list[str]:
        issues: list[str] = []
        lowered_name = result.name.strip().lower()
        if not result.name.strip():
            issues.append("Missing candidate name.")
        elif lowered_name in self.SECTION_HEADINGS:
            issues.append("Candidate name looks like a section heading instead of a person name.")

        if not result.email and re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
            issues.append("Email exists in text but was not extracted.")
        if not result.phone and re.search(r"1[3-9]\d{9}", text):
            issues.append("Phone number exists in text but was not extracted.")
        if re.search(r"教育|education", text, re.IGNORECASE) and not result.education:
            issues.append("Education section exists in text but education list is empty.")
        if re.search(r"项目|project", text, re.IGNORECASE) and not result.projects:
            issues.append("Project section exists in text but project list is empty.")
        if re.search(r"技能|skills|certificate|证书", text, re.IGNORECASE) and not (result.skills or result.certificates):
            issues.append("Skill or certificate section exists in text but no skills/certificates were extracted.")

        for item in result.education:
            if re.search(r"校园经历|社团|体育部|宿舍", item.description):
                issues.append("Education item appears to include campus/student organization experience.")
                break

        return issues

    def _score(self, issues: list[str]) -> float:
        score = 1.0 - min(len(issues) * 0.12, 0.84)
        return round(max(score, 0.0), 2)
