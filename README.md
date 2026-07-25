# OpenAI / ChatGPT OAuth Batch Importer

Automate OpenAI OAuth authorization flows using Camoufox (anti-detection
headless browser). Import accounts into a compatible API gateway pool
(chatgpt2api / new-api / one-api / similar) automatically.

## How it works

```
 API Gateway        Script (Camoufox)       Mail Reader
 ┌──────────┐      ┌──────────────┐      ┌──────────┐
 │          │──────│  oauth/start │      │          │
 │          │◄─────│  auth URL    │      │          │
 │          │      │              │      │          │
 │          │      │  fill email  │      │          │
 │          │      │  fill pass   │      │          │
 │          │      │  submit      │─────│ poll code│
 │          │      │◄─────────────│      │  6-digit │
 │          │──────│  callback    │      │          │
 │          │◄─────│  oauth/finish│      │          │
 └──────────┘      └──────────────┘      └──────────┘
```

## Requirements

| Dependency | Source |
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

# 2. Clone dependencies alongside this repo
git clone https://github.com/asz798838958/freeAgentIdentity.git ../freeAgentIdentity

# 3. Configure accounts (create accounts.json)
cp accounts.example.json accounts.json
# Edit accounts.json with your actual email/password pairs

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

1. **oauth/start** — API gateway generates an authorize URL.
2. **Browser** — Camoufox fills email + password, submits.
3. **Verification code** — Polls mail-reader API until a new 6-digit code arrives.
4. **About-you** — freeAgentIdentity handles name/birthdate/age if required.
5. **Callback** — Captures `auth/callback?code=...` URL.
6. **oauth/finish** — Exchanges callback for access + refresh tokens.

## Files

```
├── oauth_batch_importer.py   # Main script
├── accounts.example.json     # Example config (copy to accounts.json)
├── accounts.json             # Your actual credentials (gitignored)
├── .gitignore
└── README.md
```

## License

MIT", "path": "/home/youyang/.cache/hermes-tmp/grok-oauth-batch/README.md"}