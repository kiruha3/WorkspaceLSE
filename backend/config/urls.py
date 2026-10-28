from django.urls import path,include
from apps.accounts.views import csrf_view, login_view, logout_view, MeView
from apps.accounts.api import PermissionsView, RoleListView, RoleDetailView, RolePermissionsView
from apps.personnel.api import EmployeeListView, EmployeeDetailView, EmployeeSpecialtiesView, SpecialtyQualifyView, EmployeeRolesView, EmployeeEffectiveView
from apps.references.api import ReferenceListView, ReferenceDetailView
from apps.personnel.api import EmployeeOrgAssignmentsView, OrgAssignmentDetailView, EmployeeRoleDetailView, EmployeeAccountView
from apps.personnel.api import AccessEmployeeDirectoryView
from apps.reports.api import Form151View

urlpatterns = [
    path("api/v1/reports/form151/",Form151View.as_view()),
    path("api/v1/reports/form151/xlsx/",Form151View.as_view(download=True)),
    path("api/v1/",include("apps.imports.urls")),
    path("api/v1/",include("apps.issuance.urls")),
    path("api/v1/",include("apps.correspondence.urls")),
    path("api/v1/",include("apps.expertises.urls")),
    path("api/v1/",include("apps.documents.urls")),
    path("api/v1/",include("apps.intake.urls")),
    path("api/v1/auth/csrf/",csrf_view),
    path("api/v1/auth/login/",login_view),
    path("api/v1/auth/logout/",logout_view),
    path("api/v1/me/",MeView.as_view()),
    path("api/v1/permissions/",PermissionsView.as_view()),
    path("api/v1/access/employees/",AccessEmployeeDirectoryView.as_view()),
    path("api/v1/roles/",RoleListView.as_view()),
    path("api/v1/roles/<uuid:pk>/",RoleDetailView.as_view()),
    path("api/v1/roles/<uuid:pk>/permissions/",RolePermissionsView.as_view()),
    path("api/v1/employees/",EmployeeListView.as_view()),
    path("api/v1/employees/<uuid:pk>/",EmployeeDetailView.as_view()),
    path("api/v1/employees/<uuid:pk>/specialties/",EmployeeSpecialtiesView.as_view()),
    path("api/v1/employees/<uuid:pk>/roles/",EmployeeRolesView.as_view()),
    path("api/v1/employees/<uuid:pk>/effective-access/",EmployeeEffectiveView.as_view()),
    path("api/v1/employees/<uuid:pk>/org-assignments/",EmployeeOrgAssignmentsView.as_view()),
    path("api/v1/employees/<uuid:pk>/account/",EmployeeAccountView.as_view()),
    path("api/v1/employee-org-assignments/<uuid:pk>/",OrgAssignmentDetailView.as_view()),
    path("api/v1/employee-roles/<uuid:pk>/",EmployeeRoleDetailView.as_view()),
    path("api/v1/employee-specialties/<uuid:pk>/qualify/",SpecialtyQualifyView.as_view()),
    path("api/v1/references/<str:catalog>/",ReferenceListView.as_view()),
    path("api/v1/references/<str:catalog>/<uuid:pk>/",ReferenceDetailView.as_view()),
]
