"""Real SQLite concurrency, mock provider; shared plan/explanation reservation limit."""
import os
if os.environ.get('ESEPTEP_BROWSER_QA')!='1' or 'browser-qa' not in os.environ.get('DJANGO_DB_PATH',''):
    raise SystemExit('Dedicated synthetic database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.db import close_old_connections
from django.test import override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw
from accounts.models import Calculation,ClientProject
from accounts.ai_explanation import explain
from projects.models import ProjectUpload,PlanAnalysisBudget
from projects.plan_analysis import analyze
user=User.objects.create_user('mixed-ai-budget-qa')
project=ClientProject.objects.create(user=user,title='Synthetic',city='Test',area_m2=36.5,rooms=1,repair_segment='comfort')
tasks=[]
for i in range(16):
    stream=io.BytesIO(); image=Image.new('RGB',(20,20),(i*10,30,40)); ImageDraw.Draw(image).rectangle((3,3,16,16),outline='white',width=2); image.save(stream,'PNG')
    upload=ProjectUpload.objects.create(user=user,file=SimpleUploadedFile('synthetic.png',stream.getvalue()))
    calc=Calculation.objects.create(project=project,calculator_slug='plitka-keramogranit',area_m2=4.8,rooms=1,thickness=1,segment='comfort',result_data={'materials':[]})
    tasks.extend([('plan',upload.pk),('estimate',calc.pk)])
lock=threading.Lock();calls=0

def provider(**kwargs):
    global calls
    with lock:calls+=1
    return {'status':'completed','output':[{'content':[{'type':'output_text','text':'{"document_kind":"floor_plan","floor_pages":[1],"rooms":[]}'}]}]}

def run(task):
    close_old_connections()
    try:
        return (analyze(ProjectUpload.objects.get(pk=task[1])) if task[0]=='plan' else explain(Calculation.objects.get(pk=task[1]),'ru')).pk
    finally:close_old_connections()

with override_settings(PLAN_AI_ENABLED=True,ESTIMATE_AI_ENABLED=True,OPENAI_LIVE_CONFIRMED=True,OPENAI_API_KEY='mock-only',PRODUCTION=False),patch('projects.plan_analysis.responses_create',side_effect=provider),patch('accounts.ai_explanation.responses_create',side_effect=provider):
    with ThreadPoolExecutor(max_workers=8) as pool:
        duplicate=list(pool.map(run,[tasks[1]]*8))
    assert len(set(duplicate))==1 and calls==1
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(run,tasks))
    assert calls==10,calls
    assert PlanAnalysisBudget.objects.get(pk=1).reserved_cents==200
print('PASS: duplicate explanation=1, mixed provider calls=10, shared reservation=200 cents, live calls=0')
