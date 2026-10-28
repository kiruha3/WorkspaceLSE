"""Tri-state facts for H:N of section4; absence is not confirmed evidence."""
GROUPS=('ministry','other_state','other')
REPEAT_COLUMNS=('H','I','J','K','L','M','N')

def possible_and(*values):
    return False if False in values else None if None in values else True

def aggregate(values,complete):
    return True if True in values else None if not complete or None in values else False

def repeat_summary(facts):
    nature=facts.get('appointment_nature')
    repeated=True if nature=='repeated' else False if nature in ('primary','additional') else None
    entries=facts.get('previous_conclusions') or []
    complete=facts.get('previous_complete') is True
    groups={}
    for group in GROUPS:
        matches=[None if entry.get('organization_group') is None else entry['organization_group']==group for entry in entries]
        nonconfirmed=[possible_and(match,entry.get('same_input_data'),None if entry.get('confirms_previous') is None else not entry['confirms_previous']) for entry,match in zip(entries,matches)]
        groups[group]={'present':aggregate(matches,complete),'not_confirmed':aggregate(nonconfirmed,complete)}
    return {'repeated':repeated,'groups':groups}
