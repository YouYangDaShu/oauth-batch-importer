# OpenAI / ChatGPT OAuth Batch Importer

Automate OpenAI OAuth authorization using Camoufox (anti-detection headless browser). Batch import accounts into a compatible API gateway pool (chatgpt2api / new-api / one-api).

## Important Note — Password Requirement

**OpenAI now requires passwords with at least 12 characters.** The script auto-generates 23-character strong passwords using `secrets.token_hex(10)`. The old Outlook passwords (8–11 chars) will be silently rejected by the password form.

The script uses JavaScript setters for React-controlled input fields (password, verification code, about-you form), which properly triggers React's change detection.

## How it works

```
 API Gateway        Script (Camoufox)       Mail Reader
 ┌──────────┐      ┌──────────────┐      ┌──────────┐
 │          │──────│  oauth/start │      │          │
 │          │◄─────│  auth URL    │      │          │
 │          │      │              │      │          │
 │          │      │  fill email  │      │          │
 │          │      │  fill pass   │      │          │
 │          │      │  submit (JS) │─────│ poll code│
 │          │      │◄─────────────│      │  6-digit │
 │          │──────│  callback    │      │          │
 │          │◄─────│  oauth/finish│      │          │
 └──────────┘      └──────────────┘      └──────────┘
```

## Requirements

| Dependency | Install |
|---|---|
| Python 3.11+ | — |
| Camoufox | `pip install camoufox && camoufox fetch` |
| freeAgentIdentity | `git clone https://github.com/asz798838958/freeAgentIdentity.git` |
| Mail Reader | `git clone https://github.com/YouYangDaShu/mail-reader.git` |
| API Gateway | chatgpt2api / new-api / one-api |

## Quick start

```bash
# 1. Install Camoufox
pip install camoufox
camoufox fetch

# 2. Clone dependencies
git clone https://github.com/asz798838958/freeAgentIdentity.git ../freeAgentIdentity

# 3. Configure accounts
cp accounts.example.json accounts.json
# Edit accounts.json with your email/password pairs

# 4. Set environment variables
export API_AUTH_KEY="your-api-auth-key"
export API_BASE_URL="http://127.0.0.1:3010"
export PROXY_URL="http://172.25.208.1:7897"
export MAIL_API_URL="http://127.0.0.1:8877"

# 5. Edit target emails at the bottom of oauth_batch_importer.py
#    or use: export TARGET_EMAILS="user+sub1@outlook.com,user+sub2@..."

# 6. Run
python3 oauth_batch_importer.py
```

## OAuth flow

1. **oauth/start** — API gateway generates an authorize URL with email_hint
2. **Browser** — Camoufox opens the URL. Email is pre-filled from the hint.
   - If new account: goes directly to `create-account/password`
   - If existing: goes to `log-in/password`
3. **Password** — Filled via JavaScript setter (handles React controlled inputs)
4. **Verification** — Polls mail-reader API until a new 6-digit code arrives
5. **About-you** — freeAgentIdentity handles name/birthdate/age/consent
6. **Callback** — Captures `auth/callback?code=...` URL
7. **oauth/finish** — Exchanges callback for access + refresh tokens

## Key fixes in v2

| Issue | Fix |
|---|---|
| OpenAI requires 12+ char passwords | Auto-generate 23-char passwords |
| React inputs not detecting `fill()` | Use JS property setter + dispatch events |
| Korean age-mode about-you page | freeAgentIdentity handles it |
| Verification code detection | Poll mail API, compare against pre-flow snapshot |

## Files

```
├── oauth_batch_importer.py   # Main script (v2 with fixes)
├── accounts.example.json     # Example config
├── accounts.json             # Your credentials (gitignored)
├── .gitignore
└── README.md
```

## License

MIT