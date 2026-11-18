"""Append safe placeholders only; never read or print secret values."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from dotenv import dotenv_values

class Command(BaseCommand):
    help='Prepare ignored .env for manual filling. Does not enable or call OpenAI.'
    def handle(self,*args,**options):
        path=settings.BASE_DIR/'.env'
        if path.is_symlink():raise CommandError('Refusing symlink target')
        existing=dotenv_values(path) if path.exists() else {}
        values={'OPENAI_API_KEY':'PASTE_EXISTING_ESEPTEP_KEY_HERE','OPENAI_MODEL':'gpt-5.4-mini-2026-03-17',
                'OPENAI_MAX_OUTPUT_TOKENS':'1800','OPENAI_TIMEOUT_SECONDS':'45','OPENAI_LIVE_CONFIRMED':'0',
                'PLAN_AI_ENABLED':'0','ESTIMATE_AI_ENABLED':'0'}
        additions={key:value for key,value in values.items() if key not in existing}
        if additions:
            with path.open('a',encoding='utf-8') as file:
                file.write('\n# ESEPTEP backend API: insert your existing key locally; never commit this file.\n')
                for key,value in additions.items():file.write(key+'='+value+'\n')
        self.stdout.write('Prepared .env; existing values preserved. Live requests remain subject to separate confirmation.')
