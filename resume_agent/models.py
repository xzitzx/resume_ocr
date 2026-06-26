from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Education:
    school: str = ""
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


@dataclass
class WorkExperience:
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


@dataclass
class Project:
    name: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


@dataclass
class ParseResult:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    work_experience: list[WorkExperience] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    certificates: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)
    parser: str = "rules"
    model: str = ""
    confidence_score: float = 0.0
    quality_issues: list[str] = field(default_factory=list)
    agent_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParseResult":
        return cls(
            name=str(data.get("name") or ""),
            email=str(data.get("email") or ""),
            phone=str(data.get("phone") or ""),
            location=str(data.get("location") or ""),
            summary=str(data.get("summary") or ""),
            skills=_string_list(data.get("skills")),
            education=[Education(**_known_fields(item, Education)) for item in _dict_list(data.get("education"))],
            work_experience=[
                WorkExperience(**_known_fields(item, WorkExperience))
                for item in _dict_list(data.get("work_experience"))
            ],
            projects=[Project(**_known_fields(item, Project)) for item in _dict_list(data.get("projects"))],
            certificates=_string_list(data.get("certificates")),
            languages=_string_list(data.get("languages")),
            raw_text=str(data.get("raw_text") or ""),
            warnings=_string_list(data.get("warnings")),
            parser=str(data.get("parser") or "llm"),
            model=str(data.get("model") or ""),
            confidence_score=_float_value(data.get("confidence_score")),
            quality_issues=_string_list(data.get("quality_issues")),
            agent_steps=_string_list(data.get("agent_steps")),
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _known_fields(value: dict[str, Any], model_type: type[Any]) -> dict[str, str]:
    names = set(model_type.__dataclass_fields__)
    return {key: str(value.get(key) or "") for key in names}


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
