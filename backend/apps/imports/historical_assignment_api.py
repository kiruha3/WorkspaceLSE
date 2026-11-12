from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer
from .historical_assignments import preview, apply_assignments


class SelectedWork(StrictSerializer):
    expertise_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    proposal_hash = serializers.RegexField(r'^[a-f0-9]{64}$')


class AssignmentImportInput(StrictSerializer):
    selections = SelectedWork(many=True, allow_empty=False, max_length=1000)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)

    def validate_selections(self, rows):
        if len({row['expertise_id'] for row in rows}) != len(rows):
            raise serializers.ValidationError('Работа выбрана несколько раз.')
        return rows


class HistoricalAssignmentsView(GenericAPIView):
    def get(self, request):
        return Response(preview(request.user))

    def post(self, request):
        form = AssignmentImportInput(data=request.data)
        form.is_valid(raise_exception=True)
        result = apply_assignments(actor=request.user, **form.validated_data,
            key=request.headers.get('Idempotency-Key'), payload=request.data)
        return Response(result, status=201)
