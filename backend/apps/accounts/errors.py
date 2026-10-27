from django.http import JsonResponse
from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    code = "request_error"
    fields = {}
    if response.status_code == 409:
        code = getattr(exc,"default_code","conflict")
    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "auth_required"
    elif isinstance(exc, PermissionDenied):
        code = "csrf_failed" if "CSRF" in str(exc) else "permission_denied"
    elif isinstance(exc, ValidationError):
        code = "validation_error"
        fields = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors":exc.detail}
    elif response.status_code == 404:
        code = "not_found"
    response.data = {"code":code, "message":str(getattr(exc,"detail",exc)), "field_errors":fields}
    return response


def csrf_failure(request, reason=""):
    return JsonResponse({"code":"csrf_failed","message":"Обновите страницу и повторите действие.","field_errors":{}},status=403)
