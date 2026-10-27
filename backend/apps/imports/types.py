from dataclasses import dataclass,asdict


@dataclass
class SourceRow:
    source_row:int
    raw:dict
    formulas:dict
    extra:dict


@dataclass
class Diagnostic:
    code:str
    severity:str
    columns:list[str]
    message:str


@dataclass
class NormalizedRow(SourceRow):
    facts:dict
    diagnostics:list[Diagnostic]

    @property
    def normalization_complete(self):
        return not any(item.severity=="error" for item in self.diagnostics)

    def to_dict(self):
        return {**asdict(self),"normalization_complete":self.normalization_complete}


@dataclass
class ParsedJournal:
    source_name:str
    source_kind:str
    date_system:str
    source_sha256:str
    sheet_name:str
    parser_version:str
    rows:list[NormalizedRow]
    summary:dict

    def to_dict(self):
        return {**{key:value for key,value in asdict(self).items() if key!="rows"},"rows":[row.to_dict() for row in self.rows]}
