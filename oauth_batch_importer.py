#!/home/youyang/projects/services/freeAgentIdentity/.venv/bin/python
"""Batch OAuth importer - fixed with 12+ char password generation."""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, secrets, string
from pathlib import Path
from camoufox.sync_api import Camoufox
sys.path.insert(0, "/home/youyang/projects/services/freeAgentIdentity")
from platforms.chatgpt.browser_register import _submit_about_you_via_page

AUTH = "sst009909"
BASE = "http://127.0.0.1:3010"
PROXY = "http://172.25.208.1:7897"
MAIL_API = "http://127.0.0.1:8877"
ACCTS_FILE = "/home/youyang/projects/services/outlook-mail-reader/accounts.json"

# Load passwords
ACCTS = {}
for a in json.loads(open(ACCTS_FILE).read()):
    e = (a.get("email") or "").strip().lower()
    p = (a.get("password") or "").strip()
    if e and p: ACCTS[e] = p

def gp(email):
    l, d = email.split("@")
    b = l.rsplit("+", 1)[0] if "+" in l else l
    return ACCTS.get(f"{b}@{d}".lower())

def gen_pwd():
    """Generate strong password meeting OpenAI's 12+ char requirement."""
    return "OA" + secrets.token_hex(10) + "!"  # 23 chars

def api(m, p, b=None):
    d = None if b is None else json.dumps(b).encode()
    r = urllib.request.Request(f"{BASE}{p}", data=d,
        headers={"Authorization": f"Bearer {AUTH}", "Content-Type": "application/json"}, method=m)
    with urllib.request.urlopen(r, timeout=120) as x: return json.loads(x.read().decode())

def codes(main):
    url = f"{MAIL_API}/api/mail/{urllib.parse.quote(main)}?top=12"
    with urllib.request.urlopen(url, timeout=60) as r: d = json.loads(r.read().decode())
    out = set()
    for m in d.get("emails") or d:
        s = str(m.get("subject","")) + str(m.get("from",""))
        if "openai" not in s.lower() and "chatgpt" not in s.lower(): continue
        body = str(m.get("body",""))
        text = re.sub(r"<style[\s\S]*?</style>"," ",body,flags=re.I)
        text = re.sub(r"<[^>]+>"," ",text); text = re.sub(r"\s+"," ",text)
        for p in [r"to continue:\s*(\d{6})", r"계속하세요:\s*(\d{6})", r"(\d{6})"]:
            mm = re.search(p, text, re.I)
            if mm: out.add(mm.group(1)); break
    return out

def lg(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def run_one(email):
    main = email.split("@")[0].rsplit("+", 1)[0] + "@" + email.split("@")[1]
    pwd = gen_pwd()  # Use generated strong password, not Outlook password
    lg(f"Using password: {pwd[:10]}... (len={len(pwd)})")

    try:
        s = api("POST", "/api/accounts/oauth/start", {"email_hint": email})
        sid = s["session_id"]
    except Exception as e: lg(f"FAIL {email}: start {e}"); return False

    before = codes(main)
    with Camoufox(headless=True, proxy={"server": PROXY}, geoip=True) as b:
        try:
            p = b.new_page()
            p.goto(s["authorize_url"], wait_until="domcontentloaded", timeout=120000)
            p.wait_for_timeout(3000)

            # Fill password via JS setter (handles React controlled inputs)
            p.evaluate(f"""() => {{
                const el = document.querySelector('input[type="password"]');
                if (!el) return;
                const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                el.focus();
                if (d && d.set) d.set.call(el, '{pwd}');
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }}""")

            p.wait_for_timeout(1000)
            for n in ["Continue", "계속", "Next", "Create account"]:
                btn = p.get_by_role("button", name=re.compile(n, re.I))
                if btn.count(): btn.first.click(timeout=3000); break
            p.wait_for_timeout(5000)

            nc = None
            for _ in range(30):
                fresh = [c for c in codes(main) if c not in before]
                if fresh and "email-verification" in p.url:
                    nc = fresh[0]; break
                p.wait_for_timeout(3000)
            if not nc: lg(f"FAIL {email}: no code"); return False

            # Fill verification code via JS setter
            p.evaluate(f"""() => {{
                const el = document.querySelector('input[inputmode=numeric],input[name=code],input[autocomplete=one-time-code],input[type=text]');
                if (!el) return;
                const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                el.focus();
                if (d && d.set) d.set.call(el, '{nc}'); else el.value = '{nc}';
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }}""")
            p.keyboard.press("Enter"); p.wait_for_timeout(6000)

            if "email-verification" in p.url:
                for n in ["Continue", "계속"]:
                    btn = p.get_by_role("button", name=re.compile(n, re.I))
                    if btn.count(): btn.first.click(timeout=3000); break
                p.wait_for_timeout(5000)

            for _ in range(30):
                if "about-you" in p.url or "callback" in p.url: break
                p.wait_for_timeout(1000)

            if "callback" in p.url and "code=" in p.url: cb = p.url
            elif "about-you" in p.url:
                try: p.evaluate("""() => { for (const n of ['allCheckboxes','personalInfoConsent','thirdPartyConsent','overseasTransferConsent']) { const el = document.querySelector(`input[name="${n}"]`); if (el && !el.checked) { try { el.click() } catch(e) {} } } }""")
                except: pass
                r = _submit_about_you_via_page(p, lg)
                if not r.get("ok"): lg(f"FAIL {email}: about-you {r.get('text','')[:80]}"); return False
                for _ in range(20):
                    if "callback" in p.url and "code=" in p.url: break
                    p.wait_for_timeout(1000)
                cb = p.url
            else: lg(f"FAIL {email}: {p.title()[:60]}"); return False

            if "callback" not in cb or "code=" not in cb: lg(f"FAIL {email}: no callback"); return False
            f = api("POST", "/api/accounts/oauth/finish", {"session_id": sid, "callback": cb})
            added = f.get("added") or 0
            lg(f"OK {email}: added={added}")
            return added > 0
        except Exception as e: lg(f"FAIL {email}: {e}"); return False

if __name__ == "__main__":
    emails = [
        "NapoleonNicolasumxj+s2a2@outlook.com",
    ]
    for e in emails:
        ok = run_one(e)
        lg(f"Result: {'OK' if ok else 'FAIL'}: {e}")
        time.sleep(1)
