import pytest
from apps.reports.calculation import calculate
from apps.reports.registry import calculate_registry
from test_form151_reasons import accepted_work
pytestmark=pytest.mark.django_db

def find(report,section,column):
 return next(rule for rule in report['column_rules'] if rule['section']==section and rule['column']==column)

def test_each_calculated_column_has_one_server_explanation_without_more_queries(django_assert_num_queries):
 with django_assert_num_queries(1):report=calculate_registry(year=2026,month=10)
 assert report['rules_version']
 wanted={1:set('DEFGHIJKLMNOPQRSTUVWX'),2:set('DEFGHIJKL'),3:set('DEF'),4:set('DEFGHIJKLMNOPQRST'),5:set('DEFGHIJKLMNOPQR'),6:set('DEFGHIJKLM')}
 actual={(r['section'],r['column']) for r in report['column_rules']}
 assert actual=={(s,c) for s,columns in wanted.items() for c in columns}
 assert len(actual)==len(report['column_rules'])
 for rule in report['column_rules']:
  assert rule['official_column']==ord(rule['column'])-ord('C') and rule['meaning'] and rule['unit'] and rule['sources'] and rule['period'] and rule['unknown'] and rule['limitations']

def test_rules_describe_real_period_units_evidence_and_sndz_uncertainty():
 report=calculate_registry(year=2026,month=10)
 questions=find(report,2,'D');assert questions['unit']=='вопрос' and 'questions' in ' '.join(questions['sources'])
 duration=find(report,3,'D');assert 'обе границы' in duration['meaning'] and 'приостанов' in ' '.join(duration['limitations']).casefold()
 repeat=find(report,4,'H');assert 'СНДЗ' in ' '.join(repeat['limitations']) and 'не установлен' in ' '.join(repeat['limitations'])
 confirm=find(report,4,'J');assert 'same_input_data' in ' '.join(confirm['sources']) and 'confirms_previous' in ' '.join(confirm['sources'])
 decree=find(report,1,'P');assert 'decree3214' in ' '.join(decree['sources']) and '1 и 5' in ' '.join(decree['limitations'])
 return_rule=find(report,4,'O');assert 'выдачи' in ' '.join(return_rule['limitations']) and 'решения' in return_rule['period']
 stock=find(report,1,'D');assert 'полноты' in ' '.join(stock['unknown']) and 'текущую организацию' in stock['meaning']
 plan=find(report,6,'D');assert '294' in plan['meaning'] and '2026' in plan['meaning']

def test_journal_rules_do_not_advertise_registry_only_fields(accepted_work):
 from types import SimpleNamespace
 rows=[SimpleNamespace(source_row=4,raw={},facts={'registration_number':'1/4-1-26','received_on':'2026-01-01','state':'in_progress','category_code':'1','specialty_code':'18.1'})]
 report=calculate(rows,2026,10)
 assert (4,'H') not in {(r['section'],r['column']) for r in report['column_rules']}
 assert 'сумме' in ' '.join(find(report,2,'D')['limitations']) and 'пустые' in ' '.join(find(report,2,'D')['limitations']).casefold()
 assert 'R/S/T' in ' '.join(find(report,2,'D')['sources'])
 assert 'WorkClosure' not in str(report['column_rules']) and 'classification' not in str(report['column_rules'])

def test_rules_version_is_part_of_export_revision(monkeypatch):
 from apps.reports import column_rules
 first=calculate_registry(year=2026,month=10)
 monkeypatch.setattr(column_rules,'RULES_VERSION','test-new-rule-version')
 second=calculate_registry(year=2026,month=10)
 assert second['rules_version']=='test-new-rule-version' and second['data_revision']!=first['data_revision']
