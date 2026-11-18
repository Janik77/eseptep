"""Real SQLite concurrency, mocked provider only. Never use a live API key."""
import os
if os.environ.get('ESEPTEP_BROWSER_QA') != '1' or 'browser-qa' not in os.environ.get('DJANGO_DB_PATH', ''):
    raise SystemExit('Dedicated synthetic browser-qa database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.test import override_settings
from django.contrib.auth.models import User
from django.db import close_old_connections
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from projects.models import ProjectUpload, PlanAnalysisBudget
from projects.plan_analysis import analyze

user = User.objects.create_user('plan-concurrency')
ids=[]
for i in range(16):
    file=io.BytesIO();Image.new('RGB',(20,20),(i*10,20,30)).save(file,'PNG')
    ids.append(ProjectUpload.objects.create(user=user,file=SimpleUploadedFile(f'plan-{i}.png',file.getvalue())).pk)
lock=threading.Lock()
calls=0

def provider(*args, **kwargs):
    global calls
    with lock:
        calls+=1
    return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':'{"rooms": []}'}]}]}).encode())

def execute(pk):
    close_old_connections()
    try:
        return analyze(ProjectUpload.objects.get(pk=pk)).pk
    finally:
        close_old_connections()

with override_settings(PLAN_AI_ENABLED=True,OPENAI_API_KEY='mock-only-no-network',PRODUCTION=False), patch('urllib.request.urlopen',side_effect=provider):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(execute,[ids[0]]*8))
    assert len(set(results))==1, results
    assert calls==1, calls
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(execute,ids[1:]))
    assert calls==10, calls
    assert PlanAnalysisBudget.objects.get(pk=1).reserved_cents==200
print(json.dumps({'concurrent_duplicate_calls':1,'total_mock_provider_calls':calls,'reserved_cents':200,'real_api_calls':0,'exceptions':0}))
