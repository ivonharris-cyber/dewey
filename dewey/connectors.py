"""Connectors & keys engine for the 007-Bond cockpit bottom-left hub.

Three tabs — Subscriptions, BCP, MCP — plus the honest key vault. The hard rule:
no secret VALUE is ever returned by status, logged, or written to disk in the
clear. `key_status` reports only set/missing; the vault stores fernet-encrypted
bytes and only the gated `key` broker (after a passphrase unlock + approval)
ever releases a value, to the requesting process's stdout — never to a log.
"""
from __future__ import annotations

import base64
import csv
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from . import core

MANIFEST = Path(__file__).with_name("connectors.json")
DEWEY_HOME = Path.home() / ".dewey"
EXPENSES = DEWEY_HOME / "expenses.csv"
VAULT = DEWEY_HOME / "vault.enc"
VAULT_MAGIC = b"DEWEYVAULT1\n"


# ── manifest ────────────────────────────────────────────────────────────────
def load_manifest() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data.get("connectors", [])


def _by_kind(kind: str, manifest=None) -> list[dict]:
    return [c for c in (manifest or load_manifest()) if c.get("kind") == kind]


# ── .env sources (consulted for status only) ────────────────────────────────
def env_files() -> list[Path]:
    """The .env files we consult for key *presence*. Override with DEWEY_ENV_FILES
    (os.pathsep-separated). No value ever leaves this module via status paths."""
    override = os.environ.get("DEWEY_ENV_FILES")
    if override:
        files = [Path(p).expanduser() for p in override.split(os.pathsep) if p.strip()]
    else:
        files = [
            Path.home() / ".hermes" / ".env",
            Path(os.environ.get("MANA_MASTER_ENV", r"D:\projects\hermes-cain-abel\.env")),
        ]
    return [f for f in files if f.is_file()]


def _parse_env(path: Path) -> dict:
    """Parse KEY=value pairs from a .env file. Values are used only to test
    non-emptiness / to encrypt into the vault — never returned by status."""
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.lower().startswith("export "):
                line = line[7:]
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and val:
                out[key] = val
    except OSError:
        pass
    return out


def _present_keys() -> set[str]:
    """Env KEY names present (non-empty) across os.environ + the env files."""
    present = {k for k, v in os.environ.items() if v and v.strip()}
    for f in env_files():
        present |= set(_parse_env(f).keys())
    return present


def key_status(manifest=None) -> dict:
    """Per-connector env-key presence — booleans only, never a value."""
    manifest = manifest or load_manifest()
    present = _present_keys()
    return {c["id"]: {k: (k in present) for k in c.get("env", [])} for c in manifest}


# ── expenses (local ledger) ─────────────────────────────────────────────────
def _cost_overrides() -> dict:
    out: dict[str, float] = {}
    if EXPENSES.is_file():
        with EXPENSES.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                sid = (row.get("id") or "").strip()
                try:
                    out[sid] = float(row.get("cost_month") or 0)
                except (TypeError, ValueError):
                    continue
    return out


def spend_summary(manifest=None) -> dict:
    manifest = manifest or load_manifest()
    overrides = _cost_overrides()
    items, total = [], 0.0
    for c in _by_kind("subscription", manifest):
        cost = overrides.get(c["id"], float(c.get("cost_month", 0) or 0))
        total += cost
        items.append({"id": c["id"], "name": c["name"], "cost_month": cost,
                      "currency": c.get("currency", "USD")})
    return {"items": items, "total_month": round(total, 2), "currency": "USD",
            "ledger": str(EXPENSES)}


def set_cost(sid: str, cost: float) -> None:
    """Write/replace a per-service monthly-cost override in the ledger (atomic)."""
    DEWEY_HOME.mkdir(parents=True, exist_ok=True)
    rows = {}
    if EXPENSES.is_file():
        with EXPENSES.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                sid_k = (row.get("id") or "").strip()
                if sid_k:
                    rows[sid_k] = row.get("cost_month")
    rows[sid] = cost
    body = "id,cost_month\n" + "".join(f"{k},{v}\n" for k, v in rows.items() if k)
    core._atomic_write(EXPENSES, body)


# ── BCP (Google Drive via existing rclone) ──────────────────────────────────
def _rclone_exe() -> Optional[str]:
    import shutil
    exe = shutil.which("rclone")
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        for p in Path(local).glob("Microsoft/WinGet/Packages/Rclone.Rclone*/**/rclone.exe"):
            return str(p)
    return None


def bcp_entry(manifest=None) -> dict:
    got = _by_kind("bcp", manifest)
    return got[0] if got else {}


def bcp_status(manifest=None) -> dict:
    c = bcp_entry(manifest)
    exe = _rclone_exe()
    last = ""
    log = c.get("log")
    if log and Path(log).is_file():
        try:
            last = Path(log).read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-1][:200]
        except (OSError, IndexError):
            last = ""
    return {"remote": c.get("remote", ""), "target": c.get("target", ""),
            "rclone": bool(exe), "rclone_path": exe or "", "task": c.get("task", ""),
            "last_log": last}


def bcp_backup_cmd(manifest=None, source=None) -> list[str]:
    c = bcp_entry(manifest)
    exe = _rclone_exe() or "rclone"
    src = source or str(DEWEY_HOME)
    dest = f"{c.get('remote', '')}{c.get('target', '')}"
    return [exe, "copy", src, dest, "--progress"]


def bcp_backup(manifest=None, source=None, dry_run=True) -> dict:
    cmd = bcp_backup_cmd(manifest, source) + (["--dry-run"] if dry_run else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        return {"cmd": " ".join(cmd), "ok": r.returncode == 0, "out": (r.stdout or r.stderr)[-2000:]}
    except Exception as e:  # noqa: BLE001 — surface any launch failure to the panel
        return {"cmd": " ".join(cmd), "ok": False, "out": str(e)}


# ── MCP catalogue / install ─────────────────────────────────────────────────
def mcp_list(manifest=None) -> list[dict]:
    return sorted(_by_kind("mcp", manifest), key=lambda c: c.get("popularity", 0), reverse=True)


def mcp_install_cmd(sid: str, manifest=None, library="") -> str:
    for c in _by_kind("mcp", manifest):
        if c.get("id") == sid:
            return (c.get("install") or "").replace("{library}", library)
    return ""


# ── vault (fernet, lazy import) ─────────────────────────────────────────────
def _crypto():
    try:
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        return Fernet, InvalidToken, PBKDF2HMAC, hashes
    except ImportError:
        return None


def vault_available() -> bool:
    return _crypto() is not None


def vault_exists() -> bool:
    return VAULT.is_file()


def _derive(passphrase: str, salt: bytes) -> bytes:
    _, _, PBKDF2HMAC, hashes = _crypto()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def vault_import(passphrase: str, extra: dict | None = None) -> int:
    """Encrypt current env keys (+ extra) into vault.enc (0600). Returns key count.
    Values are read only to encrypt them — never logged or returned."""
    crypto = _crypto()
    if not crypto:
        raise RuntimeError("vault needs the [vault] extra:  pip install \"dewey[vault]\"")
    Fernet = crypto[0]
    secrets = dict(extra or {})
    for f in env_files():
        secrets.update(_parse_env(f))
    salt = os.urandom(16)
    token = Fernet(_derive(passphrase, salt)).encrypt(json.dumps(secrets).encode())
    DEWEY_HOME.mkdir(parents=True, exist_ok=True)
    VAULT.write_bytes(VAULT_MAGIC + salt + token)
    try:
        os.chmod(VAULT, 0o600)
    except OSError:
        pass
    return len(secrets)


class Vault:
    """An unlocked vault held only in memory for the session."""

    def __init__(self, secrets: dict):
        self._secrets = secrets

    def names(self) -> list[str]:
        return sorted(self._secrets)

    def get(self, name: str) -> Optional[str]:
        return self._secrets.get(name)


def unlock(passphrase: str) -> Vault:
    crypto = _crypto()
    if not crypto:
        raise RuntimeError("vault needs the [vault] extra:  pip install \"dewey[vault]\"")
    Fernet, InvalidToken = crypto[0], crypto[1]
    raw = VAULT.read_bytes()
    if not raw.startswith(VAULT_MAGIC):
        raise ValueError("not a dewey vault")
    body = raw[len(VAULT_MAGIC):]
    salt, token = body[:16], body[16:]
    try:
        data = Fernet(_derive(passphrase, salt)).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("wrong passphrase") from exc
    return Vault(json.loads(data.decode()))


# ── panel state (no values, ever) ───────────────────────────────────────────
def state(manifest=None) -> dict:
    manifest = manifest or load_manifest()
    ks = key_status(manifest)
    subs = []
    for c in _by_kind("subscription", manifest):
        keys = {k: ks[c["id"]].get(k, False) for k in c.get("env", [])}
        subs.append({"id": c["id"], "name": c["name"], "powers": c.get("powers", ""),
                     "keys_url": c.get("keys_url", ""), "env": c.get("env", []),
                     "cost_month": c.get("cost_month", 0), "keys": keys,
                     "ready": all(keys.values()) if keys else True})
    return {
        "subscriptions": subs,
        "spend": spend_summary(manifest),
        "mcps": mcp_list(manifest),
        "bcp": bcp_status(manifest),
        "vault": {"available": vault_available(), "exists": vault_exists()},
    }
