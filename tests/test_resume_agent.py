from resume_agent import ResumeParseAgent
from resume_agent.llm import LLMParseError


def test_parse_sample_resume():
    result = ResumeParseAgent().parse("examples/sample_resume.txt")

    assert result.name == "张三"
    assert result.email == "zhangsan@example.com"
    assert result.phone == "13800138000"
    assert result.location == "上海"
    assert "Python" in result.skills
    assert result.education
    assert result.work_experience
    assert result.projects
    assert result.parser == "rules"


def test_llm_failure_falls_back_to_rules():
    class BrokenLLMClient:
        is_configured = True
        model = "broken-model"

        def parse_resume(self, text):
            raise LLMParseError("boom")

    result = ResumeParseAgent(llm_client=BrokenLLMClient(), use_llm=True).parse("examples/sample_resume.txt")

    assert result.parser == "rules"
    assert result.name == "张三"
    assert "LLM parsing failed" in result.warnings[0]
