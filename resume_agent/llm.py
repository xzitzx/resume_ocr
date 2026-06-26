from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ParseResult


class LLMParseError(RuntimeError):
    pass


def load_dotenv(dotenv_path: str | Path = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def parse_resume(self, text: str) -> ParseResult:
        if not self.api_key:
            raise LLMParseError("LLM_API_KEY or OPENAI_API_KEY is not configured.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(text)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        response = self._post_json(f"{self.base_url}/chat/completions", payload)
        content = self._extract_content(response)
        data = self._loads_json(content)
        result = ParseResult.from_dict(data)
        result.parser = "llm"
        result.model = self.model
        result.raw_text = text
        return result

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise LLMParseError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMParseError(f"LLM request failed: {exc}") from exc

    def _extract_content(self, response: dict[str, Any]) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMParseError(f"Unexpected LLM response: {response}") from exc

    def _loads_json(self, content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise LLMParseError("LLM response did not contain JSON.")
            data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise LLMParseError("LLM response JSON must be an object.")
        return data

    def _system_prompt(self) -> str:
        empty = asdict(ParseResult())
        empty.pop("raw_text", None)
        empty.pop("warnings", None)
        empty["education"] = [
            {"school": "", "degree": "", "major": "", "start_date": "", "end_date": "", "description": ""}
        ]
        empty["work_experience"] = [
            {"company": "", "title": "", "start_date": "", "end_date": "", "description": ""}
        ]
        empty["projects"] = [
            {"name": "", "role": "", "start_date": "", "end_date": "", "description": ""}
        ]
        return (
            "You are a strict resume parsing agent. Return only one JSON object and no Markdown.\n"
            "Extract candidate information from the resume text. Use empty strings or empty arrays for missing fields.\n"
            "Important rules:\n"
            "- The name must be the person's name, not a section heading such as 'Basic information'.\n"
            "- Put campus/student organization experience into projects only if it is project-like; do not put it into education.\n"
            "- Education items should contain only school, degree, major, dates, and relevant courses.\n"
            "- Extract skills and certificates from skill/certificate sections.\n"
            "- Do not invent facts. Preserve date formats from the source text.\n"
            "- description should keep the relevant responsibilities and achievements.\n"
            f"JSON schema example: {json.dumps(empty, ensure_ascii=False)}"
        )

    def _user_prompt(self, text: str) -> str:
        return f"Parse this resume text:\n\n{text[:30000]}"
