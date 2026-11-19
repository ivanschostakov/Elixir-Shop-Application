#!/usr/bin/env python3
"""Read chat diagnostics from the two deployment hosts without printing secrets.

Run from a normal terminal with SSH network access. The password is read with
getpass and passed to sshpass through an inherited pipe, never argv or a file.
Remote operations only inspect containers, configuration and logs, and SELECT
the migration version inside an explicitly read-only database transaction.
"""

import argparse
import ast
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HOSTS = ("5.42.110.57", "94.241.172.221")
ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "config/companion.py",
    "config/telegram.py",
    "src/app/modules/users/me/companion.py",
    "src/app/services/community/access.py",
)

CONTAINER_CHECK = r'''
import asyncio, hashlib, json, logging
from pathlib import Path
logging.disable(logging.CRITICAL)
result = {}
try:
    import config
    result["flags"] = {name: getattr(config, name, None) for name in (
        "AI_COMPANION_ENABLED", "AI_COMPANION_DIALOGUE_ENABLED", "TELEGRAM_COMMUNITY_ENABLED")}
    result["configured"] = {name: bool(getattr(config, name, None)) for name in (
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_COMMUNITY_CHAT_ID", "TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET",
        "APP_INTEGRITY_IOS_TEAM_ID", "APP_INTEGRITY_IOS_BUNDLE_ID")}
except Exception as exc:
    result["config_error"] = type(exc).__name__
root = Path("/app/backend")
if not root.is_dir():
    root = Path.cwd()
files = %FILES%
result["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in files if (root / name).is_file()}
try:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    result["image_migration_heads"] = list(ScriptDirectory.from_config(Config(str(root / "alembic.ini"))).get_heads())
except Exception as exc:
    result["migration_files_error"] = type(exc).__name__
async def database_check():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(config.ASYNC_DB_URL, echo=False)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                await connection.execute(text("SET LOCAL statement_timeout = '5000'"))
                rows = await connection.execute(text("SELECT version_num FROM alembic_version"))
                result["database_migration_heads"] = [row[0] for row in rows]
    finally:
        await engine.dispose()
try:
    asyncio.run(asyncio.wait_for(database_check(), timeout=12))
except Exception as exc:
    result["database_error"] = type(exc).__name__
print(json.dumps(result))
'''.replace("%FILES%", repr(FILES))

REMOTE_CHECK = r'''
import collections, json, re, subprocess
result = {"containers": [], "chat_http_counts": {}, "exception_counts": {}}
def command(args, timeout=20):
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout)
try:
    listing = command(["docker", "ps", "-a", "--format", "{{json .}}"])
    if listing.returncode:
        result["docker_error"] = "Docker unavailable or this SSH user has no Docker permission"
    else:
        containers = [json.loads(line) for line in listing.stdout.splitlines() if line.strip()]
        relevant = [item for item in containers if re.search(r"elixir|shop|backend", item.get("Names", "") + " " + item.get("Image", ""), re.I)]
        result["containers"] = [{key: item.get(key) for key in ("Names", "Image", "Status")} for item in relevant]
        candidates = [item for item in relevant if re.search(r"backend.*api|api.*backend|fastapi", item.get("Names", ""), re.I)]
        result["backends"] = {}
        for item in candidates[:3]:
            name = item["Names"]
            checked = command(["docker", "exec", "-e", "PYTHONDONTWRITEBYTECODE=1", "-i", name, "python", "-B", "-c", %CHECK%], timeout=35)
            try:
                result["backends"][name] = json.loads(checked.stdout)
            except (ValueError, TypeError):
                result["backends"][name] = {"inspection_error": "Container Python probe failed", "exit_code": checked.returncode}
            logs = command(["docker", "logs", "--since", "6h", "--tail", "2500", name])
            statuses, exceptions = collections.Counter(), collections.Counter()
            for line in (logs.stdout + "\n" + logs.stderr).splitlines():
                match = re.search(r'"(?:GET|POST|PUT|PATCH|DELETE) (/[^ ?"]*)(?:\?[^ "]*)? HTTP/[^\"]+"\s+(\d{3})', line)
                if match and any(part in match[1] for part in ("companion", "community", "app-integrity", "transcrib", "voice")):
                    path = re.sub(r'/\d+(?=/|$)', '/:id', match[1])
                    statuses[path + " " + match[2]] += 1
                exception = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):', line)
                if exception:
                    exceptions[exception[1]] += 1
            result["chat_http_counts"][name] = dict(statuses)
            result["exception_counts"][name] = dict(exceptions)
except Exception as exc:
    result["probe_error"] = type(exc).__name__
print(json.dumps(result))
'''.replace("%CHECK%", repr(CONTAINER_CHECK))


def local_heads():
    revisions, parents = set(), set()
    for file in (ROOT / "backend/migrations/versions").glob("*.py"):
        for node in ast.parse(file.read_text()).body:
            name = node.target.id if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            if name not in ("revision", "down_revision"):
                continue
            value = ast.literal_eval(node.value)
            if name == "revision":
                revisions.add(value)
            elif isinstance(value, str):
                parents.add(value)
            elif value:
                parents.update(value)
    return sorted(revisions - parents)


def inspect_host(host, password):
    reader, writer = os.pipe()
    try:
        os.write(writer, (password + "\n").encode())
        os.close(writer)
        writer = None
        checked = subprocess.run([
            "sshpass", "-d", str(reader), "ssh", "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "PubkeyAuthentication=no", "-o", "NumberOfPasswordPrompts=1",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
            "paylakurusyan@" + host, "python3 -B -",
        ], input=REMOTE_CHECK, text=True, capture_output=True, pass_fds=(reader,), timeout=100)
        if checked.returncode:
            # Do not include unrestricted SSH output or any remote login banner.
            reason = next((label for fragment, label in (
                ("Host key verification failed", "Host key is not verified; verify it with normal SSH first"),
                ("Permission denied", "SSH authentication failed"),
                ("Operation not permitted", "SSH networking is blocked by this execution environment"),
                ("Connection refused", "SSH port refused the connection"),
                ("timed out", "SSH connection timed out"),
            ) if fragment in checked.stderr), "SSH probe failed")
            return {"error": reason, "exit_code": checked.returncode}
        try:
            return json.loads(checked.stdout)
        except ValueError:
            return {"error": "Remote Python did not return a diagnostics report"}
    except subprocess.TimeoutExpired:
        return {"error": "Diagnostics timed out"}
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/elixir-chat-availability.json"))
    args = parser.parse_args()
    if not shutil.which("sshpass"):
        parser.exit(1, "sshpass is required.\n")
    password = getpass.getpass("SSH password (hidden): ")
    report = {
        "expected_migration_heads": local_heads(),
        "local_source_sha256": {name: hashlib.sha256((ROOT / "backend" / name).read_bytes()).hexdigest() for name in FILES},
        "servers": {},
    }
    for host in HOSTS:
        print("Checking " + host + "…", flush=True)
        report["servers"][host] = inspect_host(host, password)
    del password
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    args.output.write_text(encoded + "\n")
    print(encoded)
    print("Report: " + str(args.output))


if __name__ == "__main__":
    main()
