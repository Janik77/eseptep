#!/usr/bin/env python3
"""Upgrade the existing, isolated ESEPTEP pilot. No Nginx, credentials or live AI access."""
import argparse
from contextlib import closing
import fcntl
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path("/opt/eseptep-pilot")
CURRENT = ROOT / "current"
RELEASES = ROOT / "releases"
STATE = Path("/var/lib/eseptep-pilot")
ENV = Path("/etc/eseptep-pilot/app.env")
SERVICE = "eseptep-pilot"
SYSTEM = { "PATH":"/usr/sbin:/usr/bin:/sbin:/bin", "LANG":"C.UTF-8" }
BASE = "9880bae26a58bb6e06debf167e224ea461ba06c8"
PLAN = "c9ad68b097863e6a03b5d4c9fd680d3ed627e0a4"
CONTRACT = "6bdf3ff786a1c7818b6fd8bc716a3f6863169919"
PLAN_PATHS = ("projects/views.py", "templates/projects/upload.html")
CONTRACT_PATHS = ("templates/repairs/contract.html", "templates/repairs/detail.html")
BUDGET = "core/local_ai_budget.py"
MAX_ARCHIVE = 80 * 1024 * 1024


def require(test, reason):
    if not test:
        raise RuntimeError(reason)


def run(*args, **kwargs):
    return subprocess.run(args, check=True, env=SYSTEM, **kwargs)


def archive(data, revision):
    require(len(data) <= MAX_ARCHIVE, "Release archive exceeds size guard.")
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        require(tar.pax_headers.get("comment") == revision, "Git archive commit mismatch.")
        for member in tar:
            name = member.name
            require(not name.startswith("/") and
                    all(part not in ("", ".", "..") for part in name.split("/")),
                    "Unsafe archive path.")
            if member.isdir():
                continue
            require(member.isfile() and name not in entries, "Unsafe archive entry.")
            entries[name] = tar.extractfile(member).read()
    return entries


def write_release(entries, path):
    for name, data in entries.items():
        file = path / name
        file.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with file.open("xb") as stream:
            stream.write(data)


def compose_expected(baseline, overlays, old):
    expected = dict(baseline)
    expected.update(overlays)
    budget = expected[BUDGET]
    installed = (old / BUDGET).read_bytes()
    # The historical activation used Path.read_text/write_text on Ubuntu.
    normalized = budget.replace(b"\r\n", b"\n")
    raised = normalized.replace(b"\nCEILING = 1000\n", b"\nCEILING = 1500\n")
    require(raised != normalized, "Unknown pinned budget baseline.")
    require(installed in (budget, raised), "Unrecognized installed budget implementation.")
    expected[BUDGET] = installed
    return expected


def guard_installed(old, baseline, overlays, candidate):
    expected = compose_expected(baseline, overlays, old)
    drift = [name for name, data in expected.items()
             if not (old / name).is_file() or (old / name).is_symlink()
             or (old / name).read_bytes() != data]
    require(not drift, "Current differs from its known pinned code: " + ", ".join(drift[:12]))
    # Reject unrecorded source and templates that a tar-based refresh would omit.
    sensitive = {"accounts", "calc", "calculators", "config", "core", "projects",
                 "repairs", "templates", "static"}
    extras = []
    for name in sensitive:
        if not (old / name).is_dir():
            continue
        for f in (old / name).rglob("*"):
            parts = f.relative_to(old).parts
            if (f.is_file() and f.suffix not in (".pyc", ".pyo") and "__pycache__" not in parts
                    and f.relative_to(old).as_posix() not in expected):
                extras.append(f.relative_to(old).as_posix())
    require(not extras, "Additional installed application files: " + ", ".join(sorted(extras)[:12]))
    for name, data in overlays.items():
        require(candidate.get(name) == data, "Candidate missing exact GRACE patch: " + name)
    budget_source = baseline[BUDGET]
    require(candidate.get(BUDGET) in (budget_source, expected[BUDGET]),
            "Candidate has unrelated changes to AI ledger code.")
    # Keep the existing deployment-specific ceiling, never modify account/ledger balances.
    candidate[BUDGET] = expected[BUDGET]
    print("Preserved installed AI policy file SHA256: " +
          hashlib.sha256(candidate[BUDGET]).hexdigest(), flush=True)


def properties():
    output = run("systemctl", "show", SERVICE, "--no-pager",
                 "-p", "User", "-p", "Group", "-p", "WorkingDirectory",
                 "-p", "EnvironmentFiles", "-p", "ExecStart",
                 text=True, stdout=subprocess.PIPE).stdout
    found = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    require(found.get("User") == found.get("Group") == SERVICE, "Unexpected service identity.")
    require(found.get("WorkingDirectory") == str(CURRENT), "Unexpected current directory.")
    require(found.get("EnvironmentFiles") == str(ENV) + " (ignore_errors=no)",
            "Unexpected service environment file.")
    start = found.get("ExecStart","")
    require(str(CURRENT / ".venv/bin/gunicorn") in start and "127.0.0.1:18420" in start,
            "Unexpected ESEPTEP entrypoint.")


def system_job(path, args, *, override=(), capture=False):
    return run("systemd-run", "--quiet", "--wait", "--pipe", "--collect",
               "-p", "User=" + SERVICE, "-p", "Group=" + SERVICE,
               "-p", "WorkingDirectory=" + str(path), "-p", "EnvironmentFile=" + str(ENV),
               "-p", "PrivateNetwork=yes", "/usr/bin/env", "PYTHONDONTWRITEBYTECODE=1",
               *override, *args, **({"stdout": subprocess.PIPE, "text": True} if capture else {}))


def configuration(old):
    fields = ("DJANGO_DB_PATH", "DJANGO_PRIVATE_MEDIA_ROOT", "LOCAL_AI_BUDGET_PATH",
              "DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS", "ESEPTEP_CLOSED_PILOT",
              "DJANGO_ENV", "PLAN_AI_ENABLED", "ESEPTEP_CONTRACT_AI_ENABLED")
    data = system_job(old, ("/usr/bin/python3","-I","-c",
        f"import json,os; print(json.dumps({{k:os.getenv(k,'') for k in {fields!r}}}))"),
        capture=True).stdout
    config = json.loads(data)
    require(config["DJANGO_ALLOWED_HOSTS"] == "82.115.43.144" and
            config["DJANGO_CSRF_TRUSTED_ORIGINS"] == "https://82.115.43.144" and
            config["ESEPTEP_CLOSED_PILOT"] == "1" and config["DJANGO_ENV"] == "production",
            "Not the known closed HTTPS pilot.")
    require(config["DJANGO_DB_PATH"] == str(STATE / "demo.sqlite3") and
            config["DJANGO_PRIVATE_MEDIA_ROOT"] == str(STATE / "private"),
            "Unexpected database/private file path; stop rather than guess.")
    require(config["LOCAL_AI_BUDGET_PATH"] in ("", str(STATE / "local-ai-budget.sqlite3")),
            "Unexpected AI ledger path.")
    if config["PLAN_AI_ENABLED"] == "1" or config["ESEPTEP_CONTRACT_AI_ENABLED"] == "1":
        require(config["LOCAL_AI_BUDGET_PATH"], "Active AI is missing its ledger path.")
    return config


def sqlite_copy(source, dest):
    require(source.resolve() == source and source.is_file(), "Expected regular SQLite file: " + source.name)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)) as src:
        with closing(sqlite3.connect(dest)) as dst:
            src.backup(dst)
            require(dst.execute("pragma integrity_check").fetchall() == [("ok",)],
                    "SQLite backup integrity failure: " + source.name)
    dest.chmod(0o600)


def digest(p):
    with p.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(config, dest):
    dest.mkdir(mode=0o700)
    sqlite_copy(Path(config["DJANGO_DB_PATH"]), dest / "demo.sqlite3")
    if config["LOCAL_AI_BUDGET_PATH"]:
        ledger = Path(config["LOCAL_AI_BUDGET_PATH"])
        if ledger.exists():
            sqlite_copy(ledger, dest / ledger.name)
        else:
            require(config["PLAN_AI_ENABLED"] != "1" and config["ESEPTEP_CONTRACT_AI_ENABLED"] != "1",
                    "Active AI ledger missing.")
    source = Path(config["DJANGO_PRIVATE_MEDIA_ROOT"])
    require(source.is_dir() and source.resolve() == source, "Private upload path not found.")
    require(all(not p.is_symlink() and (p.is_file() or p.is_dir()) for p in source.rglob("*")),
            "Unexpected private upload symlink or special file.")
    shutil.copytree(source, dest / "private")
    manifest = {p.relative_to(dest).as_posix():digest(p) for p in dest.rglob("*") if p.is_file()}
    (dest / "sha256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def manage(path, *args, override=()):
    return system_job(path, (str(path / ".venv/bin/python"), "manage.py", *args), override=override)


def migrate_copy(candidate, backup, account):
    sandbox = Path(tempfile.mkdtemp(prefix="eseptep-migrate-", dir="/var/tmp"))
    try:
        os.chown(sandbox, account.pw_uid, account.pw_gid)
        db = sandbox / "demo.sqlite3"
        sqlite_copy(backup / "demo.sqlite3", db)
        os.chown(db, account.pw_uid, account.pw_gid)
        media = sandbox / "private"
        media.mkdir()
        os.chown(media, account.pw_uid, account.pw_gid)
        ledger = sandbox / "local-ai-budget.sqlite3"
        if (backup / ledger.name).exists():
            sqlite_copy(backup / ledger.name, ledger)
            os.chown(ledger, account.pw_uid, account.pw_gid)
        # No live DB/media or ledger; PrivateNetwork also bars paid calls.
        flags = (f"DJANGO_DB_PATH={db}", f"DJANGO_PRIVATE_MEDIA_ROOT={media}",
                 f"LOCAL_AI_BUDGET_PATH={ledger}")
        manage(candidate, "check", "--deploy", "--fail-level", "WARNING", override=flags)
        manage(candidate, "migrate", "--noinput", override=flags)
        manage(candidate, "migrate", "--check", override=flags)
        manage(candidate, "collectstatic", "--noinput", override=flags)
        old_names = table_names(backup / "demo.sqlite3")
        require(old_names <= table_names(db), "Migration unexpectedly removed an existing application table.")
        with closing(sqlite3.connect(db.as_uri()+"?mode=ro", uri=True)) as conn:
            require(conn.execute("pragma integrity_check").fetchall() == [("ok",)], "Migrated copy integrity failure.")
            # Only allow compatibility-preserving database changes for safe code-only rollback.
            for table in sorted(old_names):
                if table == "django_migrations":
                    continue
                before = table_info(backup / "demo.sqlite3", table)
                after = table_info(db, table)
                require(all(after.get(k) == v for k,v in before.items()),
                        "Existing column definition changed: " + table)
                require(all(k in before or not v[0] or v[1] is not None for k,v in after.items()),
                        "New required column without a DB default blocks rollback: " + table)
                q = '"' + table.replace('"', '""') + '"'
                with closing(sqlite3.connect((backup / "demo.sqlite3").as_uri()+"?mode=ro", uri=True)) as source:
                    old_count = source.execute("SELECT count(*) FROM " + q).fetchone()[0]
                require(conn.execute("SELECT count(*) FROM " + q).fetchone()[0] >= old_count,
                        "Rows disappeared from existing table: " + table)
        print("Isolated copy migrated and passed compatibility guards.", flush=True)
    finally:
        shutil.rmtree(sandbox)


def table_names(file):
    with closing(sqlite3.connect(file.as_uri()+"?mode=ro",uri=True)) as conn:
        return {row[0] for row in conn.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")}


def table_info(file, name):
    with closing(sqlite3.connect(file.as_uri()+"?mode=ro",uri=True)) as conn:
        return {row[1]:(row[3],row[4],row[2],row[5])
                for row in conn.execute("select * from pragma_table_info(?)",(name,))}


def probe():
    for _ in range(20):
        try:
            with_http = http.client.HTTPConnection("127.0.0.1", 18420, timeout=2)
            try:
                with_http.request("GET", "/", headers={"Host":"82.115.43.144","X-Forwarded-Proto":"https"})
                response = with_http.getresponse()
                target = response.getheader("Location","")
                require(response.status == 302 and target.startswith("/accounts/login/"),
                        "Anonymous root must require sign-in.")
                response.read()
                with_http.request("GET", target, headers={"Host":"82.115.43.144","X-Forwarded-Proto":"https"})
                if with_http.getresponse().status == 200:
                    return
            finally:
                with_http.close()
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("Loopback pilot login health check failed.")


def point_to(release):
    new_link = ROOT / (".current.new-" + str(os.getpid()))
    new_link.symlink_to(release)
    try:
        os.replace(new_link, CURRENT)
    finally:
        new_link.unlink(missing_ok=True)


def read_inputs(args):
    baseline = archive(args.baseline.read_bytes(), BASE)
    plan = archive(args.plan.read_bytes(), PLAN)
    contract = archive(args.contract.read_bytes(), CONTRACT)
    candidate = archive(args.candidate.read_bytes(), args.sha)
    overlays = {k:plan[k] for k in PLAN_PATHS} | {k:contract[k] for k in CONTRACT_PATHS}
    return baseline, overlays, candidate


def prepare_stage(args, candidate):
    release = RELEASES / ("eseptep-" + args.sha[:12])
    require(not release.exists() and not release.is_symlink(), "Exact release directory already exists; do not reuse unverified files.")
    release.mkdir(mode=0o755)
    write_release(candidate, release)
    try:
        acct = pwd.getpwnam(SERVICE)
        venv = release / ".venv"
        static = release / "staticfiles"
        for owned in (venv, static):
            owned.mkdir()
            os.chown(owned, acct.pw_uid, acct.pw_gid)
        as_pilot = ("runuser", "-u", SERVICE, "--")
        run(*as_pilot, "/usr/bin/python3.12", "-m", "venv", str(venv))
        python = str(venv / "bin/python")
        run(*as_pilot, python, "-m", "pip", "--disable-pip-version-check", "--no-cache-dir",
            "install", "-r", "requirements-hosted-pilot.txt", cwd=release)
        run(*as_pilot, python, "-m", "pip", "check", cwd=release)
        for f in [venv, *venv.rglob("*")]:
            os.chown(f, 0, 0, follow_symlinks=False)
        require(digest(release / BUDGET) == hashlib.sha256(candidate[BUDGET]).hexdigest(),
                "Staged AI policy file does not match the deployed policy.")
        return release
    except Exception:
        raise RuntimeError("Preparation failed; inactive candidate left at " + str(release)) from None


def upgrade(args):
    require(os.geteuid() == 0, "Run under sudo to control only the pilot service.")
    require(re.fullmatch(r"[0-9a-f]{40}", args.sha), "Pin a full 40-hex commit.")
    os.umask(0o022)
    require(CURRENT.is_symlink() and CURRENT.resolve().parent == RELEASES and ENV.is_file(),
            "Unsupported existing pilot layout.")
    properties()
    lockpath = "/run/eseptep-pilot-install.lock"
    with open(lockpath, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run("systemctl","is-active","--quiet", SERVICE)
        old = CURRENT.resolve(strict=True)
        before_env = digest(ENV)
        before, overlay, candidate = read_inputs(args)
        guard_installed(old, before, overlay, candidate)
        cfg = configuration(old)
        new = prepare_stage(args, candidate)
        account = pwd.getpwnam(SERVICE)
        backup_root = ROOT / "backups"
        backup_root.mkdir(mode=0o700,exist_ok=True)
        require(backup_root.resolve() == backup_root and backup_root.stat().st_uid == 0 and
                backup_root.stat().st_mode & 0o077 == 0, "Backups directory is not root-private.")
        name = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + args.sha[:12]
        rehearsal = backup_root / (name + "-rehearsal")
        snapshot(cfg, rehearsal)
        migrate_copy(new, rehearsal, account)
        require(digest(ENV) == before_env and CURRENT.resolve() == old, "Pilot configuration changed during rehearsal.")
        guard_installed(old, before, overlay, candidate)
        if not args.apply:
            print("PREFLIGHT OK; no service stopped, no live migration. Release candidate: " + str(new))
            return
        backup = backup_root / name
        stopped = False
        try:
            stopped = True
            run("systemctl","stop",SERVICE)
            snapshot(cfg, backup)
            (backup / "prior-release.txt").write_text(str(old)+"\n", encoding="utf-8")
            print("Verified SQLite/private snapshots: "+str(backup), flush=True)
            require(digest(ENV) == before_env and CURRENT.resolve() == old, "Pilot settings drifted before activation.")
            manage(new,"migrate","--noinput")
            manage(new,"migrate","--check")
            point_to(new)
            run("systemctl","start",SERVICE)
            probe()
            require(digest(ENV) == before_env, "Pilot settings changed during activation.")
            stopped = False
            print("ESEPTEP RELEASE OK "+args.sha)
        finally:
            if stopped:
                run("systemctl","stop",SERVICE)
                point_to(old)
                run("systemctl","start",SERVICE)
                probe()
                print("Prior release restored. Keep backups; no writable DB was replaced.", file=sys.stderr)


def interrupted(number, frame):
    raise RuntimeError("Upgrade interrupted by signal " + str(number))


def main():
    for number in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(number, interrupted)
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("baseline","plan","contract","candidate"):
        p.add_argument("--"+key, type=Path, required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--apply",action="store_true",
                   help="After isolated verification, replace only ESEPTEP current and start ESEPTEP.")
    args = p.parse_args()
    try:
        upgrade(args)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f"ESEPTEP UPGRADE STOPPED: {error}")


if __name__ == "__main__":
    main()