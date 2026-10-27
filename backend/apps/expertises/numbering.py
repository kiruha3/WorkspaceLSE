import re
from dataclasses import dataclass
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class ParsedNumber:
    sequence: int
    department_code: str
    category_code: str
    year: int
    normalized: str


def parse_current_number(number: str) -> ParsedNumber:
    match = re.fullmatch(r"([1-9][0-9]{0,8})/([1-9][0-9]*)-([1-6])-([0-9]{2})", number.strip())
    if match is None:
        raise ValidationError({"registration_number":"Введите текущий номер в формате N/отдел-категория-ГГ. Старый номер укажите отдельно."})
    seq, dept, category, year = match.groups()
    return ParsedNumber(int(seq),dept,category,2000+int(year),f"{int(seq)}/{dept}-{category}-{year}")
