"""Install a pinned, invite-only ESEPTEP release on loopback for an IPv4 HTTPS host."""
import argparse
import fcntl
import hashlib
import http.client
import io
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import ipaddress
import subprocess as sp
import sys
import tarfile
import tempfile
import time



TAG = '9880bae'
SHA = '9880bae26a58bb6e06debf167e224ea461ba06c8'
DIGEST = 'a18586013dffd69f62b0d2496bd62a15ea696cc433a6f56687a27c8fb67bae34'
ACCOUNT = 'eseptep-pilot'
UNIT = ACCOUNT + '.service'
OPT = Path('/opt/eseptep-pilot')
RELEASE = OPT / 'releases' / ('eseptep-' + TAG)
CURRENT = OPT / 'current'
CONF = Path('/etc/eseptep-pilot')
STATE = Path('/var/lib/eseptep-pilot')
UNITFILE = Path('/etc/systemd/system') / UNIT
MARK = OPT / '.bootstrap-revision'
CLEAN = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'}
PORT = 18420


def run(*args, **opts):
    return sp.run(args, check=True, env=opts.pop('env', CLEAN), **opts)


def present(p):
    return os.path.lexists(p)


def probe(host):
    conn = http.client.HTTPConnection('127.0.0.1', PORT, timeout=2)
    headers = {'Host': host, 'X-Forwarded-Proto':'https'}
    try:
        conn.request('GET','/',headers=headers)
        page = conn.getresponse()
        location = page.getheader('Location', '')
        if page.status != 302 or not location.startswith('/accounts/login/'):
            return False
        page.read()
        conn.request('GET',location,headers=headers)
        return conn.getresponse().status == 200
    except OSError:
        return False
    finally:
        conn.close()


def nginx_summary(host):
    print('NGINX PUBLIC ROUTES (read only)', flush=True)
    result = sp.run(['nginx','-T'], env=CLEAN, capture_output=True, text=True)
    if result.returncode:
        print('nginx -T failed. Inspect sudo nginx -t on this host.')
        return
    name = ''
    shown = ''
    for line in result.stdout.splitlines():
        if line.startswith('# configuration file '):
            name = line.rsplit(':',1)[0].split('file ',1)[1]
        m = re.match(r'^\s*(listen|server_name)\s+([^;{}]+);', line)
        if m:
            if shown != name:
                print(name)
                shown = name
            print(' ', m[1], m[2])
    try:
        response = sp.run(['openssl','s_client','-connect','127.0.0.1:443','-noservername'],
                          input=b'',capture_output=True,env=CLEAN,timeout=5)
        check = sp.run(['openssl','x509','-noout','-subject','-checkip', host],
                       input=response.stdout, stdout=sp.PIPE,stderr=sp.DEVNULL,env=CLEAN)
        if check.stdout:
            print(check.stdout.decode(errors='replace').strip())
    except (OSError, sp.TimeoutExpired):
        print('Default TLS certificate could not be inspected.')


def read_release(packed):
    # Hash the complete file list and contents independently of the Git tar format.
    files = {}
    digest = hashlib.sha256()
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:') as archive:
        for entry in archive:
            if entry.isdir():
                continue
            name = entry.name
            if (not entry.isfile() or name in files or name.startswith('/') or
                    any(part in ('', '.', '..') for part in name.split('/'))):
                raise SystemExit('Invalid path or file type in the release archive.')
            files[name] = archive.extractfile(entry).read()
    for name in sorted(files):
        digest.update(name.encode() + b'\0' + hashlib.sha256(files[name]).digest())
    if digest.hexdigest() != DIGEST:
        raise SystemExit('The source files do not match the pinned Git release.')
    return files


def public_source(files):
    if not RELEASE.exists():
        releases = RELEASE.parent
        releases.mkdir(exist_ok=True, mode=0o755)
        with tempfile.TemporaryDirectory(dir=releases) as tmp:
            folder = Path(tmp) / RELEASE.name
            for name, contents in files.items():
                dest = folder / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(contents)
            folder.rename(RELEASE)
    if not present(CURRENT):
        CURRENT.symlink_to(RELEASE)
    if CURRENT.resolve() != RELEASE:
        raise SystemExit('Pilot current points at another release. Aborting.')


def app_settings(host):
    example = RELEASE / 'ops/closed-pilot.env.example'
    dst = CONF / 'app.env'
    if not dst.exists():
        text = example.read_text().replace('PILOT_HOSTNAME_REPLACE_ME', host).replace(
            'DJANGO_SECRET_KEY=\n','DJANGO_SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
        with tempfile.NamedTemporaryFile(dir=CONF, mode='w',delete=False) as f:
            f.write(text.rstrip() + "\nGUNICORN_CMD_ARGS=--no-control-socket\n")
        os.replace(f.name,dst)
    return dict(s.split('=',1) for s in dst.read_text().splitlines() if s and not s.startswith('#'))


def install(host):
    os.umask(0o022)
    if os.geteuid() or not Path('/run/systemd/system').is_dir():
        raise SystemExit('A systemd-based Ubuntu server and sudo are required.')
    for binary in ['ss','nginx','systemctl','runuser','useradd','python3.12']:
        if not shutil.which(binary,path=CLEAN['PATH']):
            raise SystemExit('Required on this server: '+binary)
    packed = sys.stdin.buffer.read(64 * 1024 * 1024)
    source = read_release(packed)
    lock = open('/run/eseptep-pilot-install.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
    paths = (OPT, CONF, STATE, UNITFILE)
    owned = MARK.is_file() and MARK.read_text().strip() == SHA
    try:
        acct = pwd.getpwnam(ACCOUNT)
    except KeyError:
        acct = None
    registered = sp.run(['systemctl','show',UNIT,'--property=LoadState','--value'],env=CLEAN,capture_output=True,text=True).stdout.strip()
    if not owned and (any(present(p) for p in paths) or acct or registered != 'not-found'):
        raise SystemExit('Existing pilot installation detected. Stopped before changing it.')
    if registered not in ('not-found','loaded'):
        raise SystemExit('Existing unit has an unexpected state: '+registered)
    listening = run('ss','-H','-lnt','sport = :18420',capture_output=True,text=True).stdout
    active = sp.run(['systemctl','is-active','--quiet',UNIT],env=CLEAN).returncode == 0
    if listening or active:
        if owned and active and probe(host):
            print('ESEPTEP LOCAL OK', flush=True)
            nginx_summary(host)
            return
        raise SystemExit('Port 18420 or service is already in use. No process was stopped.')
    py = shutil.which('python3.12',path=CLEAN['PATH'])
    with tempfile.TemporaryDirectory() as testdir:
        if sp.run([py,'-m','venv',testdir],env=CLEAN,stdout=sp.DEVNULL).returncode:
            raise SystemExit('Install python3.12-venv (sudo apt install python3.12-venv) and run again.')
    if not owned:
        OPT.mkdir(mode=0o755)
        MARK.write_text(SHA+'\n')
    public_source(source)
    if not acct:
        run('useradd','--system','--user-group','--no-create-home','--home-dir',str(STATE),'--shell','/usr/sbin/nologin',ACCOUNT)
        acct = pwd.getpwnam(ACCOUNT)
    if acct.pw_uid == 0 or acct.pw_dir != str(STATE) or acct.pw_shell != '/usr/sbin/nologin':
        raise SystemExit('Pilot service account does not match installer settings.')
    CONF.mkdir(mode=0o700,exist_ok=True)
    if not STATE.exists():
        STATE.mkdir(mode=0o700)
        os.chown(STATE,acct.pw_uid,acct.pw_gid)
    settings = app_settings(host)
    if settings.get('DJANGO_ALLOWED_HOSTS') != host or settings.get('DJANGO_CSRF_TRUSTED_ORIGINS') != 'https://' + host:
        raise SystemExit('Existing configuration uses a different HTTPS host.')
    if any(settings.get(k) != '0' for k in ('PLAN_AI_ENABLED','ESEPTEP_CONTRACT_AI_ENABLED','OPENAI_LIVE_CONFIRMED')) or settings.get('OPENAI_API_KEY') or settings.get('DJANGO_DB_PATH') != str(STATE/'demo.sqlite3'):
        raise SystemExit('Customized pilot environment found. Use the existing release procedure.')
    def as_service(*args, django=False):
        env = dict(CLEAN,HOME=str(STATE),PYTHONDONTWRITEBYTECODE='1',PIP_NO_CACHE_DIR='1')
        if django:
            env.update(settings)
        return run('runuser','--preserve-environment','-u',ACCOUNT,'--',*args,cwd=RELEASE,env=env)
    venv = RELEASE/'.venv'
    for path in (venv, RELEASE/'staticfiles'):
        if not path.exists():
            path.mkdir(mode=0o755)
            os.chown(path,acct.pw_uid,acct.pw_gid)
    as_service('mkdir','-p','-m','700',str(STATE/'private'))
    as_service(py,'-m','venv',str(venv))
    python = str(venv/'bin/python')
    as_service(python,'-m','pip','install','--quiet','--disable-pip-version-check','-r','requirements-hosted-pilot.txt')
    as_service(python,'-m','pip','check')
    as_service(python,'manage.py','check','--deploy','--fail-level','WARNING',django=True)
    as_service(python,'manage.py','migrate','--noinput','--verbosity','0',django=True)
    as_service(python,'manage.py','collectstatic','--noinput','--verbosity','0',django=True)
    unit_data = (RELEASE/'ops/eseptep-pilot.service.example').read_bytes()
    if UNITFILE.exists() and UNITFILE.read_bytes() != unit_data:
        raise SystemExit('Existing service configuration differs. Stopped.')
    if not UNITFILE.exists():
        UNITFILE.write_bytes(unit_data)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now',UNIT)
    for _ in range(24):
        if probe(host):
            print('ESEPTEP LOCAL OK',flush=True)
            nginx_summary(host)
            return
        time.sleep(0.5)
    raise SystemExit('Pilot login check failed. Inspect sudo systemctl status eseptep-pilot --no-pager')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', type=ipaddress.IPv4Address)
    parser.add_argument('--install', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    host = str(args.host)
    if args.install:
        install(host)
        return
    script = Path(__file__).resolve()
    # Git reads the user's clone without root privileges. Only validated bytes
    # are written to /opt. Ignore changes to the application working tree.
    source = run('git', '-C', script.parent.parent, '--no-replace-objects',
                 'archive', '--format=tar', SHA, stdout=sp.PIPE).stdout
    read_release(source)
    run('sudo', '-v')
    run('sudo', '/usr/bin/python3', '-I', str(script), host, '--install', input=source)


if __name__ == '__main__':
    main()
