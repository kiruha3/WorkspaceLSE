from .models import LetterKind, DispatchChannel, ControlClosureReason


def seed_correspondence_catalogs():
    for code, name in [
        ("request", "Запрос"), ("reply", "Ответ"), ("information", "Информационное письмо"),
        ("other", "Прочая переписка"), ("extension_motion", "Ходатайство о продлении срока"),
        ("notification", "Уведомление"), ("cover_letter", "Сопроводительное письмо"),
    ]:
        LetterKind.objects.get_or_create(code=code, defaults={"name": name})
    for code, name in [("email", "Электронная почта"), ("russian_post", "Почта России"), ("in_person", "Нарочно"), ("edi", "Электронный документооборот")]:
        DispatchChannel.objects.get_or_create(code=code, defaults={"name": name})
    for code, name, rule in [
        ("reply_sent", "Завершающий ответ отправлен", "reply_sent"),
        ("reply_received", "Завершающий ответ получен", "reply_received"),
        ("request_withdrawn", "Запрос отозван", "withdrawn"),
        ("no_reply_required", "Ответ не требуется", "not_required"), ("other", "Иное решение", "other"),
    ]:
        ControlClosureReason.objects.get_or_create(code=code, defaults={"name": name, "rule": rule})
