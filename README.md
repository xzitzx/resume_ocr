# 简历解析 Agent

这是一个可接入大模型的简历解析 agent。它会读取简历文件，抽取文本，优先调用大模型做结构化解析；没有配置大模型时，会自动使用本地规则解析兜底。

## 支持能力

- 支持 OpenAI Chat Completions 兼容接口。
- 支持 `.txt` / `.md`，可直接运行。
- 可选支持 `.pdf`、`.docx`、图片 OCR。
- 自动抽取姓名、邮箱、手机号、技能、教育经历、工作经历、项目经历、证书、语言等字段。
- 带 agent 工作流：文本质量检查、结构化解析、结果校验、必要时二次修复、置信度评分。
- 大模型解析失败时可选择报错或回退到本地规则解析。

## 快速开始

```bash
python -m resume_agent.cli examples/sample_resume.txt
```

接入大模型：

```bash
copy .env.example .env
python -m resume_agent.cli examples/sample_resume.txt --llm
```

然后编辑 `.env`：

```text
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

`.env` 会被程序自动读取，且已加入 `.gitignore`，不要提交真实密钥。

也可以临时使用系统环境变量：

```bash
set LLM_API_KEY=你的密钥
set LLM_MODEL=gpt-4o-mini
python -m resume_agent.cli examples/sample_resume.txt --llm
```

接入 OpenAI-compatible 服务：

```bash
set LLM_API_KEY=你的密钥
set LLM_BASE_URL=https://api.openai.com/v1
set LLM_MODEL=gpt-4o-mini
python -m resume_agent.cli examples/sample_resume.txt --llm
```

输出到文件：

```bash
python -m resume_agent.cli examples/sample_resume.txt -o output.json
```

安装完整文件解析依赖：

```bash
pip install -e ".[full]"
```

图片 OCR 还需要本机安装 Tesseract OCR。

## 上传 PDF 解析

安装接口和 PDF 解析依赖：

```bash
pip install -e ".[full]"
```

启动上传服务：

```bash
python -m uvicorn resume_agent.api:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

也可以直接调用接口：

```bash
curl -F "file=@你的简历.pdf" -F "use_llm=true" http://127.0.0.1:8000/parse
```

解析并写入数据库：

```bash
curl -F "file=@你的简历.pdf" -F "use_llm=true" -F "save=true" http://127.0.0.1:8000/parse
```

默认使用 SQLite，数据库文件是 `data/resumes.sqlite3`。可以通过 `.env` 修改：

```text
RESUME_DB_PATH=data/resumes.sqlite3
```

根据返回的 `id` 查询历史解析结果：

```bash
curl http://127.0.0.1:8000/resumes/1
```

## Python 调用

```python
from resume_agent import ResumeParseAgent

agent = ResumeParseAgent(use_llm=True)
result = agent.parse("examples/sample_resume.txt")
print(result.to_dict())
```

## MCP 工具

安装 MCP 依赖：

```bash
pip install -e ".[mcp]"
```

启动 MCP server：

```bash
resume-agent-mcp
```

也可以直接用 Python 启动：

```bash
python -m resume_agent.mcp_server
```

可用工具：

- `parse_resume_file`：传入本地简历文件路径，返回结构化 JSON。
- `extract_resume_text`：只抽取简历原文文本，用来检查 PDF/OCR 抽取效果。

MCP 配置示例：

```json
{
  "mcpServers": {
    "resume-parse-agent": {
      "command": "python",
      "args": ["-m", "resume_agent.mcp_server"],
      "cwd": "C:/Users/zhangxu/Desktop/workspace/jianli_ocr",
      "env": {
        "LLM_API_KEY": "你的密钥",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL": "gpt-4o-mini"
      }
    }
  }
}
```

## 输出结构

```json
{
  "name": "张三",
  "email": "zhangsan@example.com",
  "phone": "13800138000",
  "location": "上海",
  "summary": "...",
  "skills": ["Python", "OCR", "FastAPI"],
  "education": [],
  "work_experience": [],
  "projects": [],
  "certificates": [],
  "languages": [],
  "raw_text": "...",
  "warnings": [],
  "parser": "llm",
  "model": "gpt-4o-mini",
  "confidence_score": 0.88,
  "quality_issues": [],
  "agent_steps": [
    "plan: extract text, parse, validate, repair if useful, finalize",
    "extract_text: 1200 characters",
    "text_quality: ok",
    "parse: llm (gpt-4o-mini)",
    "validate_result: ok"
  ]
}
```
