from .models import SndzReason, UnresolvedQuestionReason, ReturnReason

# Semantic identifiers, not coordinates in the spreadsheet. Existing edits stay.
RESULT_CATALOGS = (
    (SndzReason, {
        "outside_expert_knowledge": "Поставленные вопросы выходят за пределы специальных знаний эксперта",
        "materials_insufficient_addition_refused": "Объекты исследований и материалы дела непригодны или недостаточны для проведения исследования и дачи заключения и эксперту отказано в их дополнении",
        "science_cannot_answer": "Современный уровень развития науки не позволяет ответить на поставленные вопросы",
    }),
    (UnresolvedQuestionReason, {
        "methods_insufficient": "Недостаточная разработанность методик",
        "materials_insufficient": "Недостаточность представленных материалов",
        "objects_uninformative": "Недостаточная информативность объектов исследования",
        "other": "Иные",
    }),
    (ReturnReason, {
        "no_technical_facilities": "Отсутствие материально-технической базы",
        "no_required_specialist": "Отсутствие эксперта конкретной специальности",
        "no_special_conditions": "Отсутствие специальных условий",
        "appointing_party_request": "По запросу органа или лица, назначившего экспертизу",
        "other": "Иные причины",
    }),
)


def seed_result_catalogs():
    for model, items in RESULT_CATALOGS:
        for code, name in items.items():
            model.objects.get_or_create(code=code, defaults={"name": name})
