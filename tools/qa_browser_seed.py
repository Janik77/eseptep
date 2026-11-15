"""Create only synthetic data in an explicitly separate browser QA database."""
import os
from pathlib import Path
if os.environ.get('ESEPTEP_BROWSER_QA') != '1' or 'browser-qa' not in os.environ.get('DJANGO_DB_PATH', ''):
    raise SystemExit('Explicit isolated browser-qa DB required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth.models import User
from accounts.models import UserProfile, ClientProject
user = User.objects.create_user(username='browser-qa@example.test', email='browser-qa@example.test', password='Synthetic-QA-Only-815!')
UserProfile.objects.create(user=user, role='client')
ClientProject.objects.create(user=user, title='QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', city='Шымкент', area_m2=60, rooms=2)
