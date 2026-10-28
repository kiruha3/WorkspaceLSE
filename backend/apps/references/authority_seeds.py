"""Stable mappings of the existing journal vocabulary, never name guessing."""
from apps.imports.normalization import label

AUTHORITY_TYPES = (
    ('courts_general', 'Суды общей юрисдикции', 'court'),
    ('arbitration_courts', 'Арбитражные суды', 'court'),
    ('sk', 'Следственные органы СК РФ', 'sk'),
    ('mvd', 'Органы МВД России', 'mvd'), ('fsb', 'Органы ФСБ России', 'fsb'),
    ('fts', 'Федеральная таможенная служба России', 'fts'),
    ('fssp', 'Органы ФССП России', 'fssp'),
    ('individual', 'Физические лица', 'individual'),
    ('legal', 'Юридические лица', 'legal'), ('other', 'Иные органы и лица', 'other'),
)
LEGACY_CODES = {
    'суды общей юрисдикции': 'courts_general', 'арбитражные суды': 'arbitration_courts',
    'следственные органы ск рф': 'sk', 'органы мвд россии': 'mvd',
    'органы фсб россии': 'fsb', 'федеральная таможенная служба россии': 'fts',
    'органы фтс россии': 'fts', 'органы фссп россии': 'fssp',
    'физ.лица': 'individual', 'юр.лица': 'legal',
}

def legacy_authority_code(value):
    return LEGACY_CODES.get(label(value))
