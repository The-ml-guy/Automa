# Automa — Frequently Asked Questions

> Last updated: 2026-11-01

---

## 1. If I build a mobile app, can it do the same within the app?

**Yes, as a client-server setup.**

- **The Recommended Architecture**: Automa runs on a server, cloud VPS, or your computer as the engine. Your mobile app (built with React Native, Flutter, Swift, etc.) connects to Automa's REST API (`/api/posts`, `/api/publish`, `/media/...`).
- From your phone, you can preview the generated cards, approve/reject posts, edit captions, and tap single buttons like **"Share to Instagram"**, **"Share to LinkedIn"**, or **"Share to X"**.
- *Why not run the entire Python engine directly inside iOS/Android?* Mobile operating systems sleep background apps to save battery and cannot run headless Chromium (Playwright) or persistent SQLite cron workers natively. Having Automa run as the backend and your mobile app as the handheld dashboard gives you a private Buffer/Hootsuite.

---

## 2. If I deploy it to Railway or a free VPS, can it run by itself?

**Yes, and it runs even better there.**

- **No more tunnels needed**: On a cloud server (Railway, Render, or a free VPS like Oracle Cloud Always Free), your server gets a permanent public HTTPS address. Meta and Instagram can fetch `/media/*` directly without needing Cloudflare tunnels.
- **True 24/7 Autonomy**: It will discover research, generate editorial cards, and publish on schedule even when your personal laptop is completely powered off.
- *Note for Railway/Docker*: You just need to use the official Playwright base image (`mcr.microsoft.com/playwright/python`) so headless Chromium has all Linux graphics libraries installed.

---

## 3. Can GitHub Actions run this easily?

**Yes.**

- You can create a GitHub Actions workflow with a scheduled cron trigger (e.g. `cron: '0 9,15,21 * * *'`).
- **How it works**:
  1. Store your API keys in **GitHub Secrets** (`GEMINI_API_KEY`, `INSTAGRAM_ACCESS_TOKEN`, etc.).
  2. The workflow checks out the repo, installs dependencies, and runs `python -m automa.cli run-pipeline`.
- *One detail for Instagram on GitHub Actions*: Because GitHub Action runners destroy themselves after the job finishes, images uploaded to Instagram need to be hosted on a persistent free bucket (such as Cloudflare R2 or Supabase Storage, both 100% free) so Meta has time to pull them.

---

## 4. Are the agents implemented and working in the project?

**Yes, the full multi-agent pipeline is active and tested:**

| Agent | File | Purpose |
|-------|------|---------|
| Discovery Agent | `automa/agents/discovery.py` | Scans ArXiv, GitHub trending, HuggingFace, and tech feeds |
| Verification Agent | `automa/agents/verification.py` | Fact-checks papers and flags exaggerated hype |
| Ranking Agent | `automa/agents/ranking.py` | Scores topics across 6 technical dimensions |
| Researcher Agent | `automa/agents/researcher.py` | Distills complex technical papers into 7 core architectural questions |
| Strategist Agent | `automa/agents/strategist.py` | Selects platform angles (Benchmark, Deep-Dive, Breakdown) |
| Copywriter Agent | `automa/agents/copywriter.py` | Writes platform-tailored copy and builds visual card briefs |
| Orchestrator | `automa/agents/orchestrator.py` | Coordinates all agents end-to-end |

All agent behaviors are verified in `tests/test_multi_agent.py`.

---

## 5. How does the system access `.env` and how secure is it?

### How it accesses `.env`
- The Python `dotenv` library loads `.env` into memory at startup. The web server, publisher, and agents read API keys from `os.getenv()`.

### How secure is it from the outside world?

1. **Strictly Local**: `.env` never leaves your local computer.
2. **Git Ignored**: `.env` is listed in `.gitignore`, preventing it from ever being pushed to public GitHub repositories.
3. **Tunnel Firewall**: In `automa/web/server.py`, external requests through Cloudflare cannot access the dashboard or administrative endpoints (`403 Forbidden`). Only `/media/*.png` is served publicly.
4. **Log Masking**: Automa includes an internal `SecretScrubber` that sanitizes tokens from logs and database audit entries.

### Security Boundary Summary

| Endpoint | Local Access | External (Tunnel) Access |
|----------|-------------|-------------------------|
| `/` (Dashboard UI) | ✅ Allowed | ❌ 403 Forbidden |
| `/api/status` | ✅ Allowed | ❌ 403 Forbidden |
| `/api/posts` | ✅ Allowed | ❌ 403 Forbidden |
| `/api/publish` | ✅ Allowed | ❌ 403 Forbidden |
| `/api/generate` | ✅ Allowed | ❌ 403 Forbidden |
| `/media/*.png` | ✅ Allowed | ✅ Allowed (for Meta crawlers) |

---

## 6. Are generated images permanently stored or auto-deleted?

- **Currently permanently stored** in `content/media/` and `content/queue/`.
- Each image is approximately 400 KB to 750 KB.
- They are **not auto-deleted** right now so that:
  - You can view, download, or reuse them in the Share Center at any time.
  - If a social API fails or rate-limits, the post can retry publishing without wasting time or tokens re-rendering.
- *If disk space becomes an issue*, a retention cleanup script can be added to delete images older than 30 or 60 days.

---

## 7. Why was this built, and can a beginner use it by just changing `.env`?

### Why it was built
To have an autonomous, personal technical publishing engine. Instead of paying $30–$100/month for marketing SaaS tools (Buffer, Canva, Jasper, Hootsuite) and spending hours manually formatting graphics, Automa automatically:

1. Tracks technical breakthroughs (ArXiv, GitHub, HuggingFace)
2. Summarizes and fact-checks them
3. Designs high-resolution branded graphics
4. Distributes them across LinkedIn, X, and Instagram

### Can a beginner use it?

**Yes, absolutely.** Any beginner only needs to:

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Add their tokens to `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_key
   INSTAGRAM_ACCESS_TOKEN=your_ig_token
   INSTAGRAM_ACCOUNT_ID=your_ig_account_id
   LINKEDIN_ACCESS_TOKEN=your_linkedin_token
   LINKEDIN_PERSON_URN=urn:li:person:your_id
   X_CONSUMER_KEY=your_x_key
   X_CONSUMER_SECRET=your_x_secret
   X_ACCESS_TOKEN=your_x_token
   X_ACCESS_TOKEN_SECRET=your_x_token_secret
   ```
4. Launch the dashboard:
   ```bash
   python -m automa.web.server
   ```
   Or run the CLI:
   ```bash
   python -m automa.cli run-pipeline
   ```

The engine will run discovery, card rendering, and publishing for their accounts without changing any Python code.

