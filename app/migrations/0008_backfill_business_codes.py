import re

from django.db import migrations


CYRILLIC_TO_LATIN = str.maketrans(
    {
        "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
        "Ж": "ZH", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
        "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
        "Ф": "F", "Х": "H", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SCH",
        "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "YU", "Я": "YA",
        "а": "A", "б": "B", "в": "V", "г": "G", "д": "D", "е": "E", "ё": "E",
        "ж": "ZH", "з": "Z", "и": "I", "й": "Y", "к": "K", "л": "L", "м": "M",
        "н": "N", "о": "O", "п": "P", "р": "R", "с": "S", "т": "T", "у": "U",
        "ф": "F", "х": "H", "ц": "TS", "ч": "CH", "ш": "SH", "щ": "SCH",
        "ъ": "", "ы": "Y", "ь": "", "э": "E", "ю": "YU", "я": "YA",
        "Қ": "Q", "қ": "Q", "Ғ": "G", "ғ": "G", "Ҳ": "H", "ҳ": "H",
        "Ў": "O", "ў": "O",
    }
)


def sanitize_code(value):
    transliterated = (value or "").translate(CYRILLIC_TO_LATIN).upper()
    return re.sub(r"[^A-Z0-9]", "", transliterated)


def base_business_code(value, default, max_length=6):
    transliterated = (value or "").translate(CYRILLIC_TO_LATIN).upper()
    tokens = re.findall(r"[A-Z0-9]+", transliterated)
    if not tokens:
        return default[:max_length]

    if len(tokens) >= 2:
        initials = "".join(token[0] for token in tokens[:3])
        if len(initials) >= 2:
            return initials[:max_length]

    cleaned = "".join(tokens)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: min(3, max_length)]


def unique_code(model_cls, source, default, used_codes, pk, max_length=6):
    base = base_business_code(source, default=default, max_length=max_length)
    candidate = base
    suffix = 2
    existing_codes = set(
        model_cls.objects.exclude(pk=pk).exclude(code__isnull=True).values_list("code", flat=True)
    )

    while candidate in used_codes or candidate in existing_codes:
        suffix_text = str(suffix)
        candidate = f"{base[:max_length - len(suffix_text)]}{suffix_text}"
        suffix += 1

    used_codes.add(candidate)
    return candidate


def format_sequence(value, width):
    if not value:
        return "0" * width
    return f"{int(value):0{width}d}"


def refresh_codes_and_risk_numbers(apps, schema_editor):
    Department = apps.get_model("app", "Department")
    Category = apps.get_model("app", "Category")
    Risk = apps.get_model("app", "Risk")

    used_department_codes = set()
    for department in Department.objects.all().order_by("id"):
        source = (department.keycloak_path or "").rstrip("/").split("/")[-1] or department.name
        code = unique_code(
            Department,
            source=source,
            default="DEP",
            used_codes=used_department_codes,
            pk=department.pk,
        )
        Department.objects.filter(pk=department.pk).update(code=code)

    used_category_codes = set()
    for category in Category.objects.all().order_by("id"):
        code = unique_code(
            Category,
            source=category.name,
            default="CAT",
            used_codes=used_category_codes,
            pk=category.pk,
        )
        Category.objects.filter(pk=category.pk).update(code=code)

    category_codes = dict(Category.objects.values_list("id", "code"))
    department_codes = dict(Department.objects.values_list("id", "code"))

    for risk in Risk.objects.all().order_by("id"):
        department_id = risk.department_id or risk.responsible_department_id_id
        risk_number = "R-{category}-{department}-{sequence}".format(
            category=sanitize_code(category_codes.get(risk.category_id))[:6] or format_sequence(risk.category_id, 2),
            department=sanitize_code(department_codes.get(department_id))[:6] or format_sequence(department_id, 2),
            sequence=format_sequence(risk.id, 3),
        )
        Risk.objects.filter(pk=risk.pk).update(risk_number=risk_number)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_business_codes"),
    ]

    operations = [
        migrations.RunPython(refresh_codes_and_risk_numbers, migrations.RunPython.noop),
    ]
