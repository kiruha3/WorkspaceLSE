from django.shortcuts import get_object_or_404
from .models import Letter
from .policies import require_letter


def lock_letters(ids):
    return {letter.pk: letter for letter in Letter.objects.select_for_update().filter(pk__in=set(ids)).order_by("pk")}


def locked_letter(actor, letter_id, action, extra_ids=()):
    # Parent is immutable once the first revision exists. Read its ID first,
    # then acquire every touched anchor in the same UUID order on every path.
    anchor = get_object_or_404(Letter.objects.values("id", "current_revision__parent_id"), pk=letter_id)
    ids = [anchor["id"], *[value for value in extra_ids if value]]
    if anchor["current_revision__parent_id"]: ids.append(anchor["current_revision__parent_id"])
    letter = lock_letters(ids)[anchor["id"]]
    require_letter(actor, "letters.view", letter)
    require_letter(actor, action, letter)
    return letter
