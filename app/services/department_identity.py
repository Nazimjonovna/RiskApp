import re


DEPARTMENT_ALIASES = {
    "accounting": {"accounting", "бухгалтерия"},
    "aup": {"aup", "департамент по стратегическим проектам"},
    "billing_operations": {"billing_operations", "billing operations", "операционный департамент"},
    "chancellery": {"chancellery", "отдел делопроизводства"},
    "commerce": {"commerce", "коммерческий департамент"},
    "compliance": {
        "compliance",
        "внутренний контроль и комплаенс",
        "служба внутреннего контроля, комплаенс и рисков",
        "департамент комплаенс",
    },
    "finance": {
        "finance",
        "финансовый департамент",
        "финансовый департамент и фин контроль",
    },
    "hr": {
        "hr",
        "human resources",
        "департамент управления персоналом",
        "департамент персонала",
    },
    "ib": {
        "ib",
        "information security",
        "департамент обеспечения информационной безопасности",
        "департамент иб",
    },
    "it": {
        "it",
        "information technology",
        "департамент ит",
        "департамент информационных технологий",
    },
    "it_app_razrab": {
        "it_app_razrab",
        "it app razrab",
        "департамент по разработке программных решений",
    },
    "it_vnedreniye": {
        "it_vnedreniye",
        "it vnedreniye",
        "департамент по внедрению",
    },
    "legal": {"legal", "юридический департамент"},
    "managerial": {"managerial", "административный департамент"},
    "marketing_pr": {"marketing_pr", "marketing pr", "департамент маркетинга и продвижения"},
    "nabsovet": {"nabsovet", "аппарат наблюдательного совета"},
    "pm": {"pm", "департамент по разработке и развитию продуктов"},
    "purchasing": {
        "purchasing",
        "procurement",
        "департамент управления закупками",
        "департамент закупок",
    },
    "regional": {
        "regional",
        "отдел по работе с зарплатными проектами и региональными сотрудниками",
    },
    "risk": {"risk", "департамент управления рисками"},
    "securityaho": {"securityaho", "департамент физической безопасности"},
    "students": {"students", "департамент работы со стажёрами"},
    "ucmg": {"ucmg"},
}


def normalize_department_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = re.sub(r"[\"'`’]", "", text)
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def department_path_tail(value):
    text = str(value or "").strip().strip("/")
    if not text:
        return ""
    return normalize_department_text(text.split("/")[-1])


_CANONICAL_LOOKUP = {}
for canonical, aliases in DEPARTMENT_ALIASES.items():
    values = {canonical, canonical.replace("_", " "), *aliases}
    for alias in values:
        normalized = normalize_department_text(alias)
        if normalized:
            _CANONICAL_LOOKUP[normalized] = canonical


def canonical_department_key(value):
    normalized = normalize_department_text(value)
    if normalized in _CANONICAL_LOOKUP:
        return _CANONICAL_LOOKUP[normalized]

    tail = department_path_tail(value)
    if tail in _CANONICAL_LOOKUP:
        return _CANONICAL_LOOKUP[tail]

    if tail:
        return tail.replace(" ", "_")
    if normalized:
        return normalized.replace(" ", "_")
    return ""


def department_identity_candidates(*values):
    candidates = set()
    for value in values:
        normalized = normalize_department_text(value)
        tail = department_path_tail(value)
        canonical = canonical_department_key(value)
        if normalized:
            candidates.add(normalized)
        if tail:
            candidates.add(tail)
        if canonical:
            candidates.add(canonical)
    return candidates
