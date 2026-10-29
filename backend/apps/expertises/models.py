import uuid
import re
from django.conf import settings
from django.db import models
from django.db.models import Q,F


class ComplexGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey("intake.Material", related_name="complex_groups", on_delete=models.PROTECT)
    title = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Expertise(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey("intake.Receipt", related_name="expertises", on_delete=models.PROTECT)
    material = models.ForeignKey("intake.Material", related_name="expertises", on_delete=models.PROTECT)
    registration_number = models.CharField(max_length=100, unique=True)
    historical_number = models.CharField(max_length=300, blank=True)
    sequence = models.PositiveIntegerField()
    year = models.PositiveSmallIntegerField()
    category_code = models.CharField(max_length=1, choices=[(str(n),str(n)) for n in range(1,7)])
    department = models.ForeignKey("references.Department", on_delete=models.PROTECT)
    specialty = models.ForeignKey("references.Specialty", null=True, blank=True, on_delete=models.PROTECT)
    origin_kind = models.CharField(max_length=20, default="native", choices=[("native","Новый учёт"),("historical","Перенос журнала")])
    appointment_nature = models.CharField(max_length=20, null=True, blank=True, choices=[(s,s) for s in ("primary","repeated","additional")])
    is_commission = models.BooleanField(default=False,null=True,blank=True)
    complex_group = models.ForeignKey(ComplexGroup, null=True, blank=True, related_name="expertises", on_delete=models.PROTECT)
    state = models.CharField(max_length=25, default="in_progress", choices=[(s,s) for s in ("in_progress","suspended","completed","without_execution")])
    version = models.PositiveIntegerField(default=1)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)

    @property
    def registration_department_code(self):
        # Both native and canonical imported numbers keep their own historical
        # department. No dependency on the mutable current department FK.
        match=re.fullmatch(r"[1-9]\d*/([1-9]\d*)-[1-6]-\d{2}",self.registration_number)
        return match[1] if match else None

    class Meta:
        ordering = ["-year","-sequence","id"]
        constraints = [models.UniqueConstraint(fields=["complex_group","specialty"], name="one_work_per_complex_specialty"),
            models.CheckConstraint(condition=Q(origin_kind="historical")|Q(origin_kind="native",specialty__isnull=False,appointment_nature__isnull=False,is_commission__isnull=False),name="native_work_has_known_registration"),
            models.CheckConstraint(condition=Q(appointment_nature__isnull=True)|Q(appointment_nature__in=("primary","repeated","additional")),name="valid_appointment_nature")]


class ExpertAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expertise = models.ForeignKey(Expertise, related_name="assignments", on_delete=models.PROTECT)
    employee = models.ForeignKey("personnel.Employee", related_name="expert_assignments", on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    qualification_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ["started_at","id"]
        constraints = [models.UniqueConstraint(fields=["expertise","employee"], condition=Q(ended_at__isnull=True), name="one_current_work_assignment")]


class Suspension(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey(Expertise,related_name="suspensions",on_delete=models.PROTECT)
    suspended_on=models.DateField()
    resumed_on=models.DateField(null=True,blank=True)
    reason=models.TextField()
    resume_reason=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_suspensions",on_delete=models.PROTECT)
    resumed_by=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_resumptions",null=True,blank=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    resumed_recorded_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering=["suspended_on","created_at","id"]
        constraints=[
            models.UniqueConstraint(fields=["expertise"],condition=Q(resumed_on__isnull=True),name="one_open_work_suspension"),
            models.CheckConstraint(condition=Q(resumed_on__isnull=True)|Q(resumed_on__gte=F("suspended_on")),name="ordered_suspension_dates"),
        ]


class DeadlineEvent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey(Expertise,related_name="deadline_events",on_delete=models.PROTECT)
    kind=models.CharField(max_length=20,choices=[("initial","Исходный срок"),("request","Запрошенный срок"),("agreement","Согласованный срок")])
    recorded_on=models.DateField()
    due_on=models.DateField()
    reason=models.TextField()
    document=models.ForeignKey("documents.Document",related_name="deadline_events",null=True,blank=True,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_deadline_events",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=["recorded_on","created_at","id"]


class ResultRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey(Expertise,related_name="result_revisions",on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    kind=models.CharField(max_length=30,null=True,blank=True,choices=[("expert_conclusion","Заключение эксперта"),("research_act","Акт экспертного исследования"),("sndz","Сообщение о невозможности дать заключение")])
    completed_on=models.DateField(null=True,blank=True)
    document=models.ForeignKey("documents.Document",related_name="result_revisions",null=True,blank=True,on_delete=models.PROTECT)
    complexity_level=models.PositiveIntegerField(null=True,blank=True)
    questions=models.PositiveIntegerField(null=True,blank=True)
    categorical=models.PositiveIntegerField(null=True,blank=True)
    probable=models.PositiveIntegerField(null=True,blank=True)
    unresolved=models.PositiveIntegerField(null=True,blank=True)
    statistics_complete=models.BooleanField(default=False)
    sndz_reason=models.ForeignKey("references.SndzReason",null=True,blank=True,on_delete=models.PROTECT)
    sndz_comment=models.TextField(blank=True)
    allocations_complete=models.BooleanField(default=False)
    note=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="result_revisions",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()

    class Meta:
        ordering=["number","id"]
        constraints=[
            models.UniqueConstraint(fields=["expertise","number"],name="unique_work_result_revision"),
            models.CheckConstraint(condition=Q(complexity_level__isnull=True)|Q(complexity_level__gte=1),name="positive_result_complexity"),
        ]


class UnresolvedAllocation(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    result=models.ForeignKey(ResultRevision,related_name="unresolved_allocations",on_delete=models.PROTECT)
    reason=models.ForeignKey("references.UnresolvedQuestionReason",on_delete=models.PROTECT)
    count=models.PositiveIntegerField()
    comment=models.TextField(blank=True)
    document=models.ForeignKey("documents.Document",related_name="unresolved_allocations",null=True,blank=True,on_delete=models.PROTECT)

    class Meta:
        ordering=["reason__code","id"]
        constraints=[
            models.UniqueConstraint(fields=["result","reason"],name="unique_result_unresolved_reason"),
            models.CheckConstraint(condition=Q(count__gte=1),name="positive_unresolved_allocation"),
        ]


class WorkClosure(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey(Expertise,related_name="closures",on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    kind=models.CharField(max_length=25,choices=[("completed","Завершена"),("without_execution","Без исполнения")])
    ended_on=models.DateField()
    result=models.ForeignKey(ResultRevision,related_name="closures",null=True,blank=True,on_delete=models.PROTECT)
    document=models.ForeignKey("documents.Document",related_name="work_closures",null=True,blank=True,on_delete=models.PROTECT)
    accepted_version=models.ForeignKey("documents.FileVersion",related_name="accepted_closures",null=True,blank=True,on_delete=models.PROTECT)
    return_reason=models.ForeignKey("references.ReturnReason",null=True,blank=True,on_delete=models.PROTECT)
    comment=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_work_closures",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()

    class Meta:
        ordering=["number","id"]
        constraints=[
            models.UniqueConstraint(fields=["expertise","number"],name="unique_work_closure_revision"),
            models.CheckConstraint(condition=Q(kind="completed",result__isnull=False,return_reason__isnull=True)|Q(kind="without_execution",result__isnull=True),name="typed_work_closure"),
        ]


class HistoricalWork(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.OneToOneField(Expertise,related_name="historical",on_delete=models.PROTECT)
    source_row=models.ForeignKey("imports.ImportRow",related_name="historical_works",on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="imported_works",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    operational=models.BooleanField(default=False)
    complex_known=models.BooleanField(default=False)
    suspension_history_complete=models.BooleanField(default=False)
    statistics_confirmed=models.BooleanField(default=False)
    result_kind=models.CharField(max_length=30,null=True,blank=True,choices=[("expert_conclusion","Заключение эксперта"),("research_act","Акт исследования"),("sndz","СНДЗ")])
    completed_on=models.DateField(null=True,blank=True)
    return_decided_on=models.DateField(null=True,blank=True)
    issued_on=models.DateField(null=True,blank=True)
    complexity_level=models.PositiveIntegerField(null=True,blank=True)
    questions=models.PositiveIntegerField(null=True,blank=True)
    categorical=models.PositiveIntegerField(null=True,blank=True)
    probable=models.PositiveIntegerField(null=True,blank=True)
    unresolved=models.PositiveIntegerField(null=True,blank=True)
    amount=models.DecimalField(max_digits=18,decimal_places=2,null=True,blank=True)
    authority_type=models.TextField(blank=True)
    authority_name=models.TextField(blank=True)
    official=models.TextField(blank=True)
    contact=models.TextField(blank=True)
    basis_text=models.TextField(blank=True)
    case_description=models.TextField(blank=True)
    inventory=models.TextField(blank=True)
    executor_raw=models.TextField(blank=True)
    unresolved_note=models.TextField(blank=True)
    unresolved_reason_raw=models.TextField(blank=True)
    notes=models.TextField(blank=True)
    delivery=models.TextField(blank=True)
    sndz_reason=models.ForeignKey('references.SndzReason',null=True,blank=True,on_delete=models.PROTECT)
    sndz_comment=models.TextField(blank=True)
    allocations_complete=models.BooleanField(default=False)
    report_note=models.TextField(blank=True)
    return_reason=models.ForeignKey('references.ReturnReason',null=True,blank=True,on_delete=models.PROTECT)
    return_comment=models.TextField(blank=True)


class HistoricalUnresolvedAllocation(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    history=models.ForeignKey(HistoricalWork,related_name='unresolved_allocations',on_delete=models.PROTECT)
    reason=models.ForeignKey('references.UnresolvedQuestionReason',on_delete=models.PROTECT)
    count=models.PositiveIntegerField()
    comment=models.TextField(blank=True)
    document=models.ForeignKey('documents.Document',null=True,blank=True,on_delete=models.PROTECT)

    class Meta:
        ordering=['reason__code','id']
        constraints=[models.UniqueConstraint(fields=['history','reason'],name='unique_historical_unresolved_reason'),models.CheckConstraint(condition=Q(count__gte=1),name='positive_historical_allocation')]


class HistoricalCorrection(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    history=models.ForeignKey(HistoricalWork,related_name='corrections',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    before=models.JSONField()
    after=models.JSONField()

    class Meta:
        ordering=['number','id']
        constraints=[models.UniqueConstraint(fields=['history','number'],name='unique_historical_correction')]


class HistoricalParticipant(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    history=models.ForeignKey(HistoricalWork,related_name="participants",on_delete=models.PROTECT)
    employee=models.ForeignKey("personnel.Employee",related_name="historical_participations",on_delete=models.PROTECT)

    class Meta:
        ordering=["employee__full_name","id"]
        constraints=[models.UniqueConstraint(fields=["history","employee"],name="one_historical_participant")]


class WorkCaseDetails(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.OneToOneField(Expertise,related_name='case_details',on_delete=models.PROTECT)
    authority_type=models.ForeignKey('references.AuthorityType',null=True,blank=True,on_delete=models.PROTECT)
    authority_name=models.TextField(blank=True)
    official=models.TextField(blank=True)
    contact=models.TextField(blank=True)
    case_number=models.CharField(max_length=500,blank=True)
    case_description=models.TextField(blank=True)
    basis_text=models.TextField(blank=True)
    inventory=models.TextField(blank=True)
    questions_text=models.TextField(blank=True)
    decree3214=models.BooleanField(null=True,blank=True,default=None)
    decree_document=models.ForeignKey('documents.Document',null=True,blank=True,on_delete=models.PROTECT)
    decree_basis=models.TextField(blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=
            Q(decree3214=True,decree3214__isnull=False) |
            (Q(decree3214=False)|Q(decree3214__isnull=True))&Q(decree_document__isnull=True,decree_basis=''),
            name='case_decree_has_typed_basis')]


class CaseDetailsRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    details=models.ForeignKey(WorkCaseDetails,related_name='revisions',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    before=models.JSONField()
    after=models.JSONField()

    class Meta:
        ordering=['number','id']
        constraints=[models.UniqueConstraint(fields=['details','number'],name='unique_case_details_revision')]


class WorkClassification(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.OneToOneField(Expertise,related_name='classification',on_delete=models.PROTECT)
    previous_complete=models.BooleanField(default=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)


class PreviousConclusion(models.Model):
    GROUPS=[('ministry','ФБУ СЭУ Минюста России'),('other_state','Иные государственные СЭУ России'),('other','Иные учреждения, организации и частные эксперты')]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    classification=models.ForeignKey(WorkClassification,related_name='previous_conclusions',on_delete=models.PROTECT)
    ordinal=models.PositiveIntegerField()
    reference=models.CharField(max_length=500)
    organization_name=models.CharField(max_length=500,blank=True)
    organization_group=models.CharField(max_length=20,choices=GROUPS,null=True,blank=True)
    same_input_data=models.BooleanField(null=True,blank=True)
    confirms_previous=models.BooleanField(null=True,blank=True)
    document=models.ForeignKey('documents.Document',related_name='previous_conclusions',null=True,blank=True,on_delete=models.PROTECT)
    class Meta:
        ordering=['ordinal','id']
        constraints=[models.UniqueConstraint(fields=['classification','ordinal'],name='unique_previous_conclusion_ordinal')]


class ClassificationRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    classification=models.ForeignKey(WorkClassification,related_name='revisions',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    before=models.JSONField()
    after=models.JSONField()
    class Meta:
        ordering=['number','id']
        constraints=[models.UniqueConstraint(fields=['classification','number'],name='unique_classification_revision')]


class WorkTimingFacts(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.OneToOneField(Expertise,related_name='timing',on_delete=models.PROTECT)
    reasons_complete=models.BooleanField(default=False)
    primary_reason=models.ForeignKey('references.DelayReason',null=True,blank=True,on_delete=models.PROTECT)
    notification_sent=models.BooleanField(null=True,blank=True)
    notification_on=models.DateField(null=True,blank=True)
    notification_document=models.ForeignKey('documents.Document',related_name='timing_notifications',null=True,blank=True,on_delete=models.PROTECT)
    extension_requested=models.BooleanField(null=True,blank=True)
    request_on=models.DateField(null=True,blank=True)
    request_document=models.ForeignKey('documents.Document',related_name='timing_requests',null=True,blank=True,on_delete=models.PROTECT)
    deadline_breached=models.BooleanField(null=True,blank=True)
    breach_basis=models.TextField(blank=True)
    breach_document=models.ForeignKey('documents.Document',related_name='timing_assessments',null=True,blank=True,on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)


class TimingReason(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    timing=models.ForeignKey(WorkTimingFacts,related_name='reasons',on_delete=models.PROTECT)
    reason=models.ForeignKey('references.DelayReason',on_delete=models.PROTECT)
    comment=models.TextField(blank=True)
    document=models.ForeignKey('documents.Document',related_name='timing_reasons',null=True,blank=True,on_delete=models.PROTECT)
    class Meta:
        ordering=['reason__code','id']
        constraints=[models.UniqueConstraint(fields=['timing','reason'],name='unique_work_timing_reason')]


class TimingRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    timing=models.ForeignKey(WorkTimingFacts,related_name='revisions',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    before=models.JSONField()
    after=models.JSONField()
    class Meta:
        ordering=['number','id']
        constraints=[models.UniqueConstraint(fields=['timing','number'],name='unique_timing_revision')]
