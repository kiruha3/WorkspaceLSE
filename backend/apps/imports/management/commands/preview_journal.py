import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from apps.imports.source import parse_journal,JournalSourceError,MAX_FILE_BYTES


class Command(BaseCommand):
    help="Read the first journal sheet without writing records or source files."
    requires_system_checks=[]

    def add_arguments(self,parser):
        parser.add_argument("path")
        parser.add_argument("--include-rows",action="store_true",help="Explicitly print source case details as local JSON.")

    def handle(self,*args,**options):
        path=Path(options["path"])
        try:
            with path.open("rb") as file:content=file.read(MAX_FILE_BYTES+1)
            result=parse_journal(content,path.name).to_dict()
        except (OSError,JournalSourceError) as error:raise CommandError(str(error)) from error
        if not options["include_rows"]:result.pop("rows")
        self.stdout.write(json.dumps(result,ensure_ascii=False,indent=2))
