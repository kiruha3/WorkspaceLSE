"""Allowlisted, stable natural sorting before pagination; never modifies source rows."""
from datetime import date, datetime
from functools import cmp_to_key
import re
from rest_framework.exceptions import ValidationError

def ordering_key(params, fields):
    value=params.get('ordering','').strip()
    if value and value.removeprefix('-') not in fields:
        raise ValidationError({'ordering':'Неизвестный столбец сортировки.'})
    return value

def natural(value):
    if isinstance(value,(date,datetime)):return [(1,value.isoformat())]
    if isinstance(value,bool):return [(0,int(value))]
    if isinstance(value,(int,float)):return [(0,value)]
    return [(0,int(part)) if part.isdigit() else (1,part.casefold().replace('ё','е')) for part in re.split(r'(\d+)',str(value)) if part]

def compare(left,right,direction):
    left_blank=left is None or left==''
    right_blank=right is None or right==''
    if left_blank or right_blank:return (left_blank>right_blank)-(left_blank<right_blank)
    if isinstance(left,(tuple,list)) or isinstance(right,(tuple,list)):
        a=left if isinstance(left,(tuple,list)) else [left]
        b=right if isinstance(right,(tuple,list)) else [right]
        for i in range(max(len(a),len(b))):
            result=compare(a[i] if i<len(a) else None,b[i] if i<len(b) else None,direction)
            if result:return result
        return 0
    a,b=natural(left),natural(right)
    return direction*((a>b)-(a<b))

def ordered_rows(rows, ordering, fields):
    if not ordering:return rows
    if ordering.removeprefix('-') not in fields:raise ValidationError({'ordering':'Неизвестный столбец сортировки.'})
    getter=fields[ordering.removeprefix('-')]
    # Compute each public display key only once, including compound columns.
    decorated=[(row,getter(row)) for row in rows]
    direction=-1 if ordering.startswith('-') else 1
    return [row for row,_ in sorted(decorated,key=cmp_to_key(lambda a,b:compare(a[1],b[1],direction)))]

def paginated_data(view,request,queryset,serialize,fields):
    ordering=ordering_key(request.query_params,fields)
    if ordering:
        rows=ordered_rows(serialize(queryset),ordering,fields)
        return view.get_paginated_response(view.paginate_queryset(rows))
    return view.get_paginated_response(serialize(view.paginate_queryset(queryset)))
