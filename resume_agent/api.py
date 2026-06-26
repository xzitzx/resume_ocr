from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .agent import ResumeParseAgent
from .db import ResumeRepository
from .extractors import TextExtractionError
from .llm import LLMParseError, OpenAICompatibleClient


app = FastAPI(title="Resume Parse Agent", version="0.1.0")
repository = ResumeRepository()


@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>简历解析 Agent</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; max-width: 760px; }
      form { display: grid; gap: 16px; padding: 24px; border: 1px solid #ddd; border-radius: 8px; }
      label { display: grid; gap: 6px; }
      input, button { font-size: 16px; padding: 8px; }
      button { cursor: pointer; }
      pre { white-space: pre-wrap; background: #f6f6f6; padding: 16px; border-radius: 8px; }
    </style>
  </head>
  <body>
    <h1>简历解析 Agent</h1>
    <form id="form">
      <label>上传简历 PDF / Word / 图片 / 文本
        <input name="file" type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp" required />
      </label>
      <label>
        <span><input name="use_llm" type="checkbox" checked /> 使用大模型解析</span>
      </label>
      <label>API Key
        <input name="api_key" type="password" autocomplete="off" placeholder="可留空，留空时读取环境变量 LLM_API_KEY / OPENAI_API_KEY" />
      </label>
      <label>Base URL
        <input name="base_url" type="text" placeholder="例如 https://api.openai.com/v1，可留空" />
      </label>
      <label>Model
        <input name="model" type="text" placeholder="例如 gpt-4o-mini / deepseek-chat，可留空" />
      </label>
      <label>
        <span><input name="strict_llm" type="checkbox" checked /> 大模型失败时直接报错，不回退本地规则</span>
      </label>
      <label>
        <span><input name="save" type="checkbox" checked /> Save result to database</span>
      </label>
      <button type="submit">解析</button>
    </form>
    <pre id="result"></pre>
    <script>
      const form = document.querySelector("#form");
      const result = document.querySelector("#result");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        result.textContent = "解析中...";
        const data = new FormData(form);
        data.set("use_llm", form.use_llm.checked ? "true" : "false");
        data.set("strict_llm", form.strict_llm.checked ? "true" : "false");
        data.set("save", form.save.checked ? "true" : "false");
        const response = await fetch("/parse", { method: "POST", body: data });
        const payload = await response.json();
        result.textContent = JSON.stringify(payload, null, 2);
      });
    </script>
  </body>
</html>
"""


@app.post("/parse")
async def parse_resume(
    file: UploadFile = File(...),
    use_llm: bool = Form(True),
    strict_llm: bool = Form(True),
    api_key: str | None = Form(None),
    model: str | None = Form(None),
    base_url: str | None = Form(None),
    save: bool = Form(True),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or '<none>'}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)

        client = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
        agent = ResumeParseAgent(
            llm_client=client,
            use_llm=use_llm,
            fallback_to_rules=not strict_llm,
        )
        result = agent.parse(temp_path)
        payload = result.to_dict()
        if save:
            resume_id = repository.save(result, source_filename=file.filename or "")
            return {"id": resume_id, "result": payload}
        return payload
    except TextExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        if temp_path and temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.get("/resumes/{resume_id}")
def get_resume(resume_id: int) -> dict:
    record = repository.get(resume_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Resume record not found.")
    return record
