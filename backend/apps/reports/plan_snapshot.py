"""Coherent work + annual-plan projection, including an empty work registry.

Only ORM-generated SQL is composed; years and all other values stay bound
parameters. The outer SELECT gives both projections one PostgreSQL snapshot.
"""
import json
from django.db import connection
from django.db.models import F,OuterRef
from django.db.models.functions import JSONObject
from django.contrib.postgres.expressions import ArraySubquery
from .models import StateAssignmentPlan,StateAssignmentPlanLine

def plan_query(year):
    lines=StateAssignmentPlanLine.objects.filter(plan_id=OuterRef('pk')).order_by('specialty__code','id').annotate(
        payload=JSONObject(id=F('id'),specialty_id=F('specialty_id'),code=F('specialty__code'),name=F('specialty__name'),reference_version=F('specialty__version'),is_active=F('specialty__is_active'),count=F('count'))
    ).values('payload')
    return StateAssignmentPlan.objects.filter(year=year).annotate(payload=JSONObject(
        id=F('id'),year=F('year'),total=F('total'),version=F('version'),basis_text=F('basis_text'),document_id=F('document_id'),updated_at=F('updated_at'),lines=ArraySubquery(lines)
    )).values('payload')

def read_plan_snapshot(year):
    row=plan_query(year).first()
    return row['payload'] if row else None

def coherent_snapshot(work_queryset,fields,year):
    # Keep jsonb_build_object below PostgreSQL's100-argument limit, including
    # future work facts. Every field is a trusted ORM path, not request input.
    chunks={f'p{index}':JSONObject(**{field:F(field) for field in fields[start:start+30]}) for index,start in enumerate(range(0,len(fields),30))}
    works=work_queryset.order_by().annotate(_snapshot_key=F('pk'),_snapshot_payload=JSONObject(**chunks)).values('_snapshot_key','_snapshot_payload')
    work_sql,work_params=works.query.sql_with_params();plan_sql,plan_params=plan_query(year).query.sql_with_params()
    sql=('SELECT COALESCE((SELECT jsonb_agg(w."_snapshot_payload" ORDER BY w."_snapshot_key") FROM ('+work_sql+') w),\'[]\'::jsonb), '
         '(SELECT p."payload" FROM ('+plan_sql+') p)')
    with connection.cursor() as cursor:
        cursor.execute(sql,(*work_params,*plan_params));rows,plan=cursor.fetchone()
    # Django/psycopg may leave raw JSONB as text outside an ORM JSONField.
    rows=json.loads(rows) if isinstance(rows,str) else rows
    plan=json.loads(plan) if isinstance(plan,str) else plan
    return [{field:value for chunk in row.values() for field,value in chunk.items()} for row in rows],plan
