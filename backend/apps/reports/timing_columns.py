"""Tri-state timing facts. No inference of legal breach or outgoing delivery."""
from datetime import date

DELAY_REASON_POLICY='all'  # Owner: once in each selected report group, 2026-10-28.
DELAY_COLUMNS={'research_complexity':'G','large_material_volume':'H','expert_workload':'I','long_research_methods':'J','appointing_party_deadline':'K','other':'L'}

def delay_counts(facts,policy):
    entries=facts.get('delay_reasons') or []
    # An empty list saved before completion (or while duration was <=30) is
    # not evidence of six absent causes after a later >30-day outcome.
    complete=facts.get('delay_reasons_complete') is True and bool(entries)
    groups={item.get('report_group') for item in entries}
    unknown=any(group not in DELAY_COLUMNS for group in groups)
    all_counts={group:True if group in groups else False if complete and not unknown else None for group in DELAY_COLUMNS}
    primary=facts.get('primary_delay_reason_id')
    selected=next((item for item in entries if str(item.get('reason_id'))==str(primary)),None) if primary else None
    primary_group=selected.get('report_group') if selected else next(iter(groups)) if complete and len(groups)==1 and not unknown else None
    primary_counts={group:group==primary_group if primary_group in DELAY_COLUMNS else False if complete and not unknown and group not in groups else None for group in DELAY_COLUMNS}
    if policy=='all':return all_counts
    if policy=='primary':return primary_counts
    return {group:all_counts[group] if all_counts[group] is primary_counts[group] else None for group in DELAY_COLUMNS}

def communication_qualifies(facts,completed):
    def eligible(flag,on):
        if flag is False:return False
        try:when=date.fromisoformat(on) if isinstance(on,str) else on
        except ValueError:when=None
        if when is not None and completed is not None and when>completed:return False
        if flag is not True or when is None or completed is None:return None
        return True
    notice=eligible(facts.get('notification_sent'),facts.get('notification_on'))
    petition=eligible(facts.get('extension_requested'),facts.get('request_on'))
    return False if notice is False or petition is False else None if notice is None or petition is None else True
