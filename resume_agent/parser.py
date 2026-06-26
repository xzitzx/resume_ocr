from __future__ import annotations

import re

from .models import Education, ParseResult, Project, WorkExperience


SECTION_ALIASES = {
    "profile": ("基本信息", "个人信息", "联系方式", "profile", "contact"),
    "summary": ("个人简介", "自我评价", "职业概述", "summary", "profile summary"),
    "skills": ("技能", "专业技能", "技能清单", "技能证书", "skills", "technical skills"),
    "education": ("教育", "教育经历", "教育背景", "education"),
    "campus": ("校园经历", "社团经历", "学生工作", "在校经历"),
    "work": ("工作", "工作经历", "实习经历", "任职经历", "experience", "work experience"),
    "projects": ("项目", "项目经历", "项目经验", "projects"),
    "certificates": ("证书", "证书资质", "资格证书", "技能证书", "certificates", "certifications"),
    "languages": ("语言", "语言能力", "languages"),
}


class ResumeParser:
    EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
    PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
    DATE_RANGE_RE = re.compile(
        r"(?P<start>(?:19|20)\d{2}(?:[./年-]\d{1,2})?)\s*(?:-|--|至|到|~|—)\s*"
        r"(?P<end>至今|现在|今|present|current|(?:19|20)\d{2}(?:[./年-]\d{1,2})?)",
        re.IGNORECASE,
    )
    SKILL_SPLIT_RE = re.compile(r"[,，、/|;；\n]+")
    BULLET_RE = re.compile(r"^[\-•●⚫*]\s*")

    def parse(self, text: str, warnings: list[str] | None = None) -> ParseResult:
        normalized = self._normalize_text(text)
        sections = self._split_sections(normalized)

        result = ParseResult(raw_text=normalized, warnings=warnings or [])
        result.email = self._first_match(self.EMAIL_RE, normalized)
        result.phone = self._first_match(self.PHONE_RE, normalized)
        result.name = self._parse_name(normalized, result.email, result.phone)
        result.location = self._parse_location(normalized)
        result.summary = self._parse_summary(sections, normalized)
        result.skills = self._parse_skills(sections.get("skills", ""))
        result.education = self._parse_education(sections.get("education", ""))
        result.work_experience = self._parse_work(sections.get("work", ""))
        result.projects = self._parse_projects(sections.get("projects", ""))
        result.certificates = self._parse_certificates(
            "\n".join([sections.get("certificates", ""), sections.get("skills", "")])
        )
        result.languages = self._parse_languages(
            "\n".join([sections.get("languages", ""), sections.get("skills", "")])
        )

        if not normalized:
            result.warnings.append("No text could be extracted from the resume.")
        if not result.email and not result.phone:
            result.warnings.append("No email or phone number was detected.")

        return result

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _split_sections(self, text: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current: str | None = None

        for line in text.splitlines():
            key = self._section_key(line)
            if key:
                current = key
                sections.setdefault(current, [])
                cleaned = self._strip_heading(line)
                if cleaned and cleaned != line:
                    sections[current].append(cleaned)
                continue
            if current:
                sections[current].append(line)

        return {key: "\n".join(value).strip() for key, value in sections.items()}

    def _section_key(self, line: str) -> str | None:
        heading = re.sub(r"[:：\s#\-]+", "", line).lower()
        for key, aliases in SECTION_ALIASES.items():
            normalized_aliases = {alias.lower().replace(" ", "") for alias in aliases}
            if heading in normalized_aliases:
                return key
        for key, aliases in SECTION_ALIASES.items():
            if any(line.lower().startswith(alias.lower() + marker) for alias in aliases for marker in (":", "：")):
                return key
        return None

    def _strip_heading(self, line: str) -> str:
        return re.sub(r"^[^:：]{2,24}[:：]\s*", "", line).strip()

    def _first_match(self, pattern: re.Pattern[str], text: str) -> str:
        match = pattern.search(text)
        return match.group(0) if match else ""

    def _parse_name(self, text: str, email: str, phone: str) -> str:
        labeled = re.search(
            r"(?:姓\s*名|姓名|name)[:：]\s*([A-Za-z\u4e00-\u9fa5·]{2,30})",
            text,
            re.IGNORECASE,
        )
        if labeled:
            return labeled.group(1).strip()

        forbidden = {"基本信息", "个人信息", "联系方式", "个人简历", "简历", "personal resume", "resume"}
        for line in text.splitlines()[:10]:
            clean = line.strip()
            if not clean or clean.lower() in forbidden:
                continue
            if email and email in clean:
                continue
            if phone and phone in clean:
                continue
            if re.search(r"电话|手机|邮箱|微信|年龄|籍贯|求职意向|email|phone", clean, re.IGNORECASE):
                continue
            if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,38}|[\u4e00-\u9fa5·]{2,8}", clean):
                return clean
        return ""

    def _parse_location(self, text: str) -> str:
        labeled = re.search(
            r"(?:所在地|现居地|城市|地址|籍\s*贯|籍贯|location)[:：]\s*([^\n,，;；]{2,40})",
            text,
            re.IGNORECASE,
        )
        return labeled.group(1).strip() if labeled else ""

    def _parse_summary(self, sections: dict[str, str], text: str) -> str:
        if sections.get("summary"):
            return self._first_sentences(sections["summary"], max_chars=300)
        lines = text.splitlines()
        contact_filtered = [line for line in lines[:12] if not self.EMAIL_RE.search(line) and not self.PHONE_RE.search(line)]
        return self._first_sentences("\n".join(contact_filtered[1:]), max_chars=180)

    def _parse_skills(self, text: str) -> list[str]:
        skill_text = re.sub(r"语言能力[:：][^\n]+", "", text)
        skill_text = re.sub(r"大数据分析师（高级）|大数据分析师\(高级\)", "", skill_text)
        candidates = [item.strip(" -•●⚫*\t") for item in self.SKILL_SPLIT_RE.split(skill_text)]
        skills: list[str] = []
        for item in candidates:
            item = re.sub(r"^(办公软件|熟悉|熟练掌握)[:：]?", "", item).strip()
            if 1 < len(item) <= 50 and item not in skills and "通过大学英语" not in item:
                skills.append(item)
        return skills

    def _parse_education(self, text: str) -> list[Education]:
        entries: list[Education] = []
        for block in self._blocks(text):
            if not self._date_range(block):
                continue
            date_range = self._date_range(block)
            first_line = block.splitlines()[0]
            first_line_without_dates = self.DATE_RANGE_RE.sub("", first_line).strip(" -")
            degree = self._extract_degree(block)
            school = self._extract_school(first_line_without_dates)
            major = self._extract_major(first_line_without_dates, school, degree)
            entries.append(
                Education(
                    school=school,
                    degree=degree,
                    major=major,
                    start_date=date_range[0],
                    end_date=date_range[1],
                    description=block,
                )
            )
        return entries

    def _parse_work(self, text: str) -> list[WorkExperience]:
        entries: list[WorkExperience] = []
        for block in self._blocks(text):
            date_range = self._date_range(block)
            lines = block.splitlines()
            company = self._first_by_keywords(block, ("公司", "集团", "科技", "company", "inc", "ltd"))
            title = self._first_by_keywords(block, ("工程师", "经理", "主管", "专员", "架构师", "developer", "engineer", "manager"))
            if not company and lines:
                company = self.DATE_RANGE_RE.sub("", lines[0]).strip(" -")
            entries.append(
                WorkExperience(
                    company=company,
                    title=title,
                    start_date=date_range[0],
                    end_date=date_range[1],
                    description=block,
                )
            )
        return [entry for entry in entries if entry.description]

    def _parse_projects(self, text: str) -> list[Project]:
        entries: list[Project] = []
        for block in self._blocks(text):
            date_range = self._date_range(block)
            lines = [self.BULLET_RE.sub("", line).strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            first_line = lines[0]
            name = self.DATE_RANGE_RE.sub("", first_line).strip(" -")
            name = re.sub(r"^(项目名称|项目)[:：]\s*", "", name).strip()
            role_match = re.search(r"(?:角色|职责|role)[:：]\s*([^\n]+)", block, re.IGNORECASE)
            entries.append(
                Project(
                    name=name,
                    role=role_match.group(1).strip() if role_match else "",
                    start_date=date_range[0],
                    end_date=date_range[1],
                    description="\n".join(lines),
                )
            )
        return entries

    def _parse_certificates(self, text: str) -> list[str]:
        certificates: list[str] = []
        patterns = [
            r"大学英语[四六六四]级",
            r"大数据分析师（高级）",
            r"大数据分析师\(高级\)",
            r"软件设计师",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text):
                if match not in certificates:
                    certificates.append(match)
        return certificates

    def _parse_languages(self, text: str) -> list[str]:
        languages: list[str] = []
        if re.search(r"英语|大学英语", text):
            languages.append("英语")
        if re.search(r"中文|普通话", text):
            languages.append("中文")
        return languages

    def _date_range(self, text: str) -> tuple[str, str]:
        match = self.DATE_RANGE_RE.search(text)
        if not match:
            return "", ""
        return match.group("start"), match.group("end")

    def _blocks(self, text: str) -> list[str]:
        if not text.strip():
            return []
        parts = re.split(r"\n(?=(?:[-•●⚫*]\s*)?(?:19|20)\d{2})", text)
        blocks = [part.strip(" \n-•●⚫*\t") for part in parts if part.strip(" \n-•●⚫*\t")]
        return blocks or [text.strip()]

    def _extract_degree(self, text: str) -> str:
        for degree in ("博士", "硕士", "本科", "大专", "学士", "master", "bachelor", "phd"):
            if re.search(degree, text, re.IGNORECASE):
                return degree
        return ""

    def _extract_school(self, text: str) -> str:
        match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9·（）()]+(?:大学|学院|学校|University|College))", text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_major(self, text: str, school: str, degree: str) -> str:
        major = text.replace(school, "").replace(degree, "")
        return major.strip(" -")

    def _first_by_keywords(self, text: str, keywords: tuple[str, ...]) -> str:
        for line in text.splitlines():
            lowered = line.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                return line.strip(" -•●⚫*\t")
        return ""

    def _first_sentences(self, text: str, max_chars: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars].strip()
