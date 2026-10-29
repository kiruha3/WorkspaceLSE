import json
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework.views import APIView
from rest_framework.response import Response


@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    return JsonResponse({"csrf_token":get_token(request)})


@require_POST
@csrf_protect
def login_view(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
        username, password = data.get("username"), data.get("password")
        if not isinstance(username,str) or not isinstance(password,str):
            raise ValueError()
    except (ValueError, TypeError):
        return JsonResponse({"code":"validation_error","message":"Укажите логин и пароль.","field_errors":{}},status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"code":"invalid_credentials","message":"Неверный логин или пароль.","field_errors":{}},status=400)
    login(request,user)
    return JsonResponse({"csrf_token":get_token(request)})


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return JsonResponse({"ok":True})


class MeView(APIView):
    def get(self, request):
        from apps.personnel.models import Employee
        from .policies import access_snapshot
        employee = Employee.objects.filter(user=request.user).first()
        return Response({"id":str(request.user.id),"username":request.user.username,"employee":{"id":str(employee.id),"full_name":employee.full_name} if employee else None,"access":access_snapshot(request.user),"supported_modules":["correspondence","issuance","work_documents","journal_import_preview","journal_google_preview","journal_application","journal_source_settings","expertise_completeness","document_storage_settings"]})
