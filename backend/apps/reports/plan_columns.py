"""Pure annual-plan cells: explicit zero differs from a missing allocation."""

def plan_cells(snapshot,year,specialties):
    if snapshot is not None and snapshot['year']!=year:raise ValueError('Год плана не соответствует отчётному году.')
    lines=(snapshot or {}).get('lines',[])
    by_code={line['code']:line['count'] for line in lines}
    unknown_mapping=[code for code,count in by_code.items() if code not in specialties and count!=0]
    row_codes={}
    parents={row-1 for rows in specialties.values() for row in rows[:-1]}
    for code,rows in specialties.items():
        for row in rows:row_codes.setdefault(row-1,[]).append(code)
    values={row:sum(by_code[code] for code in codes) if not(unknown_mapping and row in parents) and all(by_code.get(code) is not None for code in codes) else None for row,codes in row_codes.items()}
    total=(snapshot or {}).get('total');values[107]=total
    known=[line['count'] for line in lines if line['count'] is not None];known_sum=sum(known)
    summary={key:(snapshot or {}).get(key) for key in ('id','total','basis_text','document_id')}
    summary.update(year=year,version=(snapshot or {}).get('version',0),known_sum=known_sum,unallocated=total-known_sum if total is not None else None,
                   line_count=len(lines),known_line_count=len(known),unknown_line_count=len(lines)-len(known))
    gaps=[]
    def gap(code,message,fields):gaps.append({'code':code,'sections':[6],'message':message,'fields':fields,'rows':[],'plan_year':year})
    if snapshot is None:gap('planMissing',f'Не указан годовой план на {year}.','state_assignment_plan')
    else:
        if total is None:gap('planTotal','Общий годовой объём не подтверждён.','state_assignment_plan.total')
        missing=[code for code in specialties if by_code.get(code) is None]
        if missing:gap('planSpecialties','Не указаны планы специальностей: '+', '.join(missing)+'. Пустое значение не равно нулю.','state_assignment_plan.lines')
        if unknown_mapping:gap('planMapping','Специальности плана не сопоставлены строкам бланка: '+', '.join(unknown_mapping)+'. Зависимые подытоги неизвестны.','state_assignment_plan.lines.specialty')
        if total is not None and known_sum!=total:gap('planAllocation',f'Общий план {total}; сумма известных строк {known_sum}. Остаток в известных строках: {total-known_sum}.','state_assignment_plan.total / lines')
    return values,summary,gaps
