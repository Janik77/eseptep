# Проверка пилотной ветки на существующем ПК

Это тестовая версия, не production. Не клонируйте проект повторно. Данные и фотографии не заменяются seed-командой. Закройте локальный runserver и фоновые процессы до резервной копии и миграции. Ниже используется имеющаяся `.venv`, без сброса локальных правок.

## PowerShell

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
if (git status --porcelain) { throw 'Есть локальные изменения: сначала сохраните их отдельно. Обновление остановлено.' }
$previous = git rev-parse HEAD
$backup = Join-Path (Split-Path (Get-Location) -Parent) ('eseptep-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
$env:ESEPTEP_BACKUP_DIR = $backup
@'
import os, shutil, sqlite3
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
root=Path(os.environ['ESEPTEP_BACKUP_DIR'])
db=Path(settings.DATABASES['default']['NAME'])
if not db.exists(): raise SystemExit('Existing database not found; stop and check configuration')
with sqlite3.connect(db) as source, sqlite3.connect(root/'database.sqlite3') as target:
    source.backup(target)
(root/'database-original-path.txt').write_text(str(db),encoding='utf-8')
for name in ('MEDIA_ROOT','PRIVATE_MEDIA_ROOT'):
    path=Path(getattr(settings,name))
    if path.exists(): shutil.copytree(path,root/name)
    (root/(name+'-original-path.txt')).write_text(str(path),encoding='utf-8')
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'Резервная копия не создана' }
$previous | Set-Content (Join-Path $backup 'previous-sha.txt')
git fetch origin feat/commercial-pilot-polish
if ($LASTEXITCODE -ne 0) { throw 'Git fetch не прошёл' }
git switch --detach FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw 'Переключение не прошло' }
git rev-parse HEAD # сверить с SHA в отчёте; при отличии остановиться
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Зависимости не установлены' }
.\.venv\Scripts\python.exe manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Проверка не прошла' }
.\.venv\Scripts\python.exe manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Миграция не прошла' }
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Открыть `http://127.0.0.1:8000/`, админку `/admin/`. Отдельный worktree для следующей разработки допустим, но эти команды не создают его. Не запускайте `qa_browser_seed.py` на этой базе: он предназначен только для новой синтетической БД CI.

## Что проверить

1. Три направления, RU/KK, все 12 форм. Для плитки неподдерживаемые сочетания «пол + крупный» и «санузел + крупный» дают объяснение, а не чужую комплектацию.
2. Плитка 36,5 м² → вариант → копирование → существующий проект → сохранить. Открыть сохранённый расчёт из кабинета.
3. После редактирования площади старый результат помечен, копирование/сохранение заблокированы до нового расчёта. Смена языка не создаёт запись.
4. Через `/admin/` создать **новую** редакцию прайса реального магазина, указав источник/дату. Сначала контрольный расчёт, затем публикация. См. `ADMIN_GUIDE_RU.md`. Не использовать синтетические цены CI как реальные.
5. Новый расчёт видит опубликованную редакцию, старый сохранённый остаётся прежним. Неполный прайс показывает неполную сумму, а не полноценную закупку.

## Откат

Остановить сервер. Сохранить новую копию текущих базы/файлов, если после обновления вводились данные. Вернуть код на SHA из `previous-sha.txt` (`git switch --detach <SHA>`) и установить его requirements. Для полного отката восстановить `database.sqlite3` в путь из `database-original-path.txt`, содержимое MEDIA_ROOT/PRIVATE_MEDIA_ROOT в соответствующие записанные пути. Делать это **только с остановленным сервером** и после проверки копий. Полное восстановление снимка удалит изменения, сделанные после него. Не использовать `git reset --hard`, `git clean` или seed для отката.

Резервные копии могут содержать личные данные: не отправляйте их в GitHub. Наличие копии не равно проверенному восстановлению на вашем ПК; сначала восстановите её в отдельной тестовой директории.
