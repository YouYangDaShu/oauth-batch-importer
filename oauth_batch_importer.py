#!/usr/bin/env python3
"""ChatGPT / OpenAI OAuth batch importer — automated browser flow.

import os
Uses Camoufox (anti-detection browser) to automate the OpenAI OAuth
authorization flow for importing accounts into a compatible API gateway
pool (chatgpt2api / one-api / new-api / similar).

Dependencies:
    pip install camoufox && camoufox fetch
    git clone https://github.com/asz798838958/freeAgentIdentity.git

The freeAgentIdentity project must be cloned as a sibling directory.
A running mail-reader service (IMAP/POP3/Graph API) is required for
verification code extraction.
"""

from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
from camoufox.sync_api import Camoufox

# ====================== CONFIGURATION ======================
AUTH_KEY = os.environ.get("API_AUTH_KEY", "your-auth-key")
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:3010")
PROXY_URL = os.environ.get("PROXY_URL", "http://172.25.208.1:7897")
MAIL_API  = os.environ.get("MAIL_API_URL", "http://127.0.0.1:8877")
# ===========================================================

sys.path.insert(0, "../freeAgentIdentity")
from platforms.chatgpt.browser_register import _submit_about_you_via_page

# ── helpers ────────────────────────────────────────────────

def _load_passwords(path="accounts.json") -> dict[str, str]:
    """Load email → password map from a JSON file."""
    out = {}
    for entry in json.loads(Path(path).read_text(encoding="utf-8")):
        email = (entry.get("email") or "").strip().lower()
        pw    = (entry.get("password") or "").strip()
        if email and pw:
            out[email] = pw
    return out

PASSWORDS = _load_passwords()

def _password_for(email: str) -> str | None:
    """Derive the main account's password from a +-suffixed sub-address."""
    local, domain = email.split("@", 1)
    base = local.rsplit("+", 1)[0] if "+" in local else local
    return PASSWORDS.get(f"{base}@{domain}".lower())

def _api(method: str, path: str, body: dict | None = None) -> dict:
    """Call the API gateway's management endpoint."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {AUTH_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def _fetch_codes(main_email: str) -> set[str]:
    """Retrieve all 6-digit verification codes from OpenAI emails
    currently present in the inbox (via the mail-reader API)."""
    url = f"{MAIL_API}/api/mail/{urllib.parse.quote(main_email)}?top=12"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode())
    found: set[str] = set()
    for msg in data.get("emails") or data:
        subject = (msg.get("subject") or "") + (msg.get("from") or "")
        if "openai" not in subject.lower() and "chatgpt" not in subject.lower():
            continue
        body = str(msg.get("body", ""))
        text = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        for pattern in [
            r"to continue:\s*(\d{6})",
            r"계속하세요:\s*(\d{6})",
            r"코드를 입력해 계속하세요:\s*(\d{6})",
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                found.add(m.group(1))
                break
        else:
            m = re.search(r"(\d{6})", text)
            if m:
                found.add(m.group(1))
    return found

def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ── core OAuth flow ────────────────────────────────────────

def import_account(email: str) -> bool:
    """Run the full OAuth authorization flow for one email address.

    Steps:
        1. POST /api/accounts/oauth/start → session_id + authorize_url
        2. Open authorize_url in Camoufox browser
        3. Fill email → Continue → fill password → Continue
        4. Wait for verification code email (poll mail-reader API)
        5. Fill code → submit → handle about-you page if present
        6. Capture callback URL → POST /api/accounts/oauth/finish
    """
    main = email.split("@")[0].rsplit("+", 1)[0] + "@" + email.split("@")[1]
    password = _password_for(email)
    if not password:
        _log(f"SKIP {email}: password not found in accounts.json")
        return False

    try:
        session = _api("POST", "/api/accounts/oauth/start",
                       {"email_hint": email})
        session_id = session["session_id"]
    except Exception as exc:
        _log(f"FAIL {email}: oauth/start → {exc}")
        return False

    codes_before = _fetch_codes(main)

    with Camoufox(headless=True, proxy={"server": PROXY_URL}, geoip=True) as browser:
        page = browser.new_page()
        try:
            page.goto(session["authorize_url"],
                      wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(2000)

            # ── fill email ──
            for sel in ['input[type="email"]', 'input[name="email"]']:
                el = page.query_selector(sel)
                if el:
                    el.fill(email)
                    break
            for label in ("Continue", "계속", "Next"):
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count():
                    btn.first.click(timeout=3000)
                    break
            page.wait_for_timeout(2000)

            # ── fill password ──
            for sel in ['input[type="password"]', 'input[name="password"]']:
                el = page.query_selector(sel)
                if el:
                    el.fill(password)
                    break
            for label in ("Continue", "계속", "Next", "Create account"):
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count():
                    btn.first.click(timeout=3000)
                    break
            page.wait_for_timeout(5000)

            # ── wait for verification code ──
            new_code = None
            for _ in range(30):
                fresh = _fetch_codes(main) - codes_before
                if fresh and "email-verification" in page.url:
                    new_code = next(iter(fresh))
                    break
                page.wait_for_timeout(3000)
            if not new_code:
                _log(f"FAIL {email}: no verification code received")
                return False

            # ── fill verification code ──
            page.evaluate(f"""((code) => {{
                const el = document.querySelector(
                    'input[inputmode=numeric],input[name=code],'
                    + 'input[autocomplete=one-time-code],input[type=text]');
                if (!el) return;
                const d = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value');
                el.focus();
                if (d && d.set) d.set.call(el, code); else el.value = code;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }})({new_code})""")
            page.keyboard.press("Enter")
            page.wait_for_timeout(6000)

            if "email-verification" in page.url:
                for label in ("Continue", "계속"):
                    btn = page.get_by_role("button",
                                           name=re.compile(label, re.I))
                    if btn.count():
                        btn.first.click(timeout=3000)
                        break
                page.wait_for_timeout(5000)

            # ── wait for about-you or callback ──
            for _ in range(30):
                if "about-you" in page.url or "callback" in page.url:
                    break
                page.wait_for_timeout(1000)

            if "callback" in page.url and "code=" in page.url:
                callback_url = page.url
            elif "about-you" in page.url:
                # tick consent checkboxes
                try:
                    page.evaluate("""() => {
                        for (const name of ['allCheckboxes',
                            'personalInfoConsent','thirdPartyConsent',
                            'overseasTransferConsent']) {
                            const el = document.querySelector(
                                `input[name="${name}"]`);
                            if (el && !el.checked) { try { el.click() }
                                catch(e) {} }
                        }
                    }""")
                except Exception:
                    pass
                result = _submit_about_you_via_page(page, _log)
                if not result.get("ok"):
                    _log(f"FAIL {email}: about-you → "
                         f"{result.get('text', '?')[:80]}")
                    return False
                for _ in range(20):
                    if "callback" in page.url and "code=" in page.url:
                        break
                    page.wait_for_timeout(1000)
                callback_url = page.url
            else:
                _log(f"FAIL {email}: unexpected page → {page.title()[:60]}")
                return False

            if "callback" not in callback_url or "code=" not in callback_url:
                _log(f"FAIL {email}: no callback URL captured")
                return False

            # ── finish OAuth ──
            finish = _api("POST", "/api/accounts/oauth/finish", {
                "session_id": session_id,
                "callback": callback_url,
            })
            added = finish.get("added", 0)
            _log(f"OK {email}: added={added}")
            return added > 0

        except Exception as exc:
            _log(f"FAIL {email}: {exc}")
            return False


# ── entry point ───────────────────────────────────────────

if __name__ == "__main__":
    import os

    # Read target emails from environment or hardcode below
    targets = os.environ.get("TARGET_EMAILS", "").split(",")
    targets = [e.strip() for e in targets if e.strip()]

    if not targets:
        # ── EDIT THIS LIST ──
        targets = [
            "your-account+s2a1@outlook.com",
            "your-account+s2a2@outlook.com",
        ]

    _log(f"Targets: {len(targets)} accounts")

    results: list[tuple[str, str]] = []
    for email in targets:
        ok = import_account(email)
        results.append((email, "OK" if ok else "FAIL"))
        time.sleep(1)

    _log("=" * 40)
    _log("SUMMARY")
    _log("=" * 40)
    for email, status in results:
        _log(f"  {status}: {email}")
    _log(f"  Total: {sum(1 for _, s in results if s == 'OK')}/"
         f"{len(results)} OK")