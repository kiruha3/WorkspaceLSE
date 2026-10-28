"""Semantic catalogue codes mapped to the preserved official template."""
SNDZ_COLUMNS={
    'outside_expert_knowledge':'G',
    'materials_insufficient_addition_refused':'H',
    'science_cannot_answer':'I',
}
UNRESOLVED_COLUMNS={
    'methods_insufficient':'I','materials_insufficient':'J',
    'objects_uninformative':'K','other':'L',
}
RETURN_COLUMNS={
    'no_technical_facilities':'P','no_required_specialist':'Q',
    'no_special_conditions':'R','appointing_party_request':'S','other':'T',
}
EXTRA_COLUMNS={1:(*SNDZ_COLUMNS.values(),'P'),2:tuple(UNRESOLVED_COLUMNS.values()),4:tuple(RETURN_COLUMNS.values())}


def unresolved_counts(facts,*,inconsistent=False):
    """A partial/unknown distribution is not a final count by reason."""
    total=facts.get('unresolved');allocations=facts.get('unresolved_allocations',[])
    if inconsistent or type(total) is not int or total<0 or not isinstance(allocations,list):return None
    counts=dict.fromkeys(UNRESOLVED_COLUMNS,0)
    if total==0:return counts if not allocations else None
    if facts.get('allocations_complete') is not True:return None
    seen=set()
    for item in allocations:
        if not isinstance(item,dict):return None
        code=item.get('reason');quantity=item.get('count')
        if not isinstance(code,str) or code not in counts or code in seen or type(quantity) is not int or quantity<1:return None
        counts[code]=quantity;seen.add(code)
    return counts if sum(counts.values())==total else None
