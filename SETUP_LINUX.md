# Job-Hunt Assistant — Linux Laptop Setup

A simple, step-by-step guide to run this on a Linux laptop (Ubuntu / Debian /
Mint / Pop!_OS). Follow it top to bottom — copy each command into the terminal.

> This is for a **laptop** (turned on and off daily). For a 24/7 server or
> Raspberry Pi with cron/systemd, see [`deploy/PI_SETUP.md`](deploy/PI_SETUP.md)
> instead.

---

## 0. Before you start

You need three things copied from the old machine (they are **not** in git):

- the whole project folder
- the **`.env`** file (your secrets) — if you don't have it, you'll create one in step 4
- your resume PDF (goes into `config/resumes/`)

> ⚠️ **Do not copy the `venv/` folder** from Windows/another machine. It is
> platform-specific and will break. We rebuild it fresh in step 3.

---

## 1. Install Python

Open a terminal and run:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

Check it worked (needs 3.10 or newer):

```bash
python3 --version
```

---

## 2. Get the project onto the laptop

Either clone it from git:

```bash
git clone <your-repo-url> job_automation
cd job_automation
```

…or if you copied the folder over a USB drive, just move into it:

```bash
cd ~/job_automation        # wherever you put it
rm -rf venv                # delete any venv copied from another OS
```

---

## 3. Create the virtual environment and install dependencies

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

This takes a couple of minutes the first time.

---

## 4. Add your secrets (`.env`)

If you already copied a `.env`, drop it in the project folder and skip ahead.
Otherwise create one from the template:

```bash
cp .env.example .env
nano .env          # edit the values, then Ctrl+O, Enter, Ctrl+X to save
```

Fill in at least:

| Setting              | What to put                                                       |
|----------------------|------------------------------------------------------------------|
| `YOUR_NAME` / `YOUR_EMAIL` / `YOUR_PHONE` | Your details.                               |
| `GMAIL_EMAIL`        | Your Gmail address.                                               |
| `GMAIL_APP_PASSWORD` | A 16-char **App Password** (not your normal password — see below). |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) → `/newbot` (optional). |
| `TELEGRAM_CHAT_ID`   | From [@userinfobot](https://t.me/userinfobot) (optional).        |
| `GROQ_API_KEY`       | Free key from <https://console.groq.com/keys> for AI scoring (optional). |

**Gmail App Password:** turn on 2-Step Verification on the Google account, then
create one at <https://myaccount.google.com/apppasswords> and paste the 16
characters into `GMAIL_APP_PASSWORD`.

Leave `DRY_RUN=true` and `REQUIRE_MAIL_CONFIRM=true` while testing — no email
will be sent automatically.

---

## 5. Add your resume

```bash
cp ~/Downloads/your-resume.pdf config/resumes/
```

Then make sure the paths in `RESUMES` inside [`config/config.py`](config/config.py)
point at that file. A single resume is fine — set every variant to the same file.

---

## 6. Test it once by hand

```bash
./venv/bin/python main.py            # one fetch across all sources
./venv/bin/python main.py --status   # print a summary of what's in the tracker
```

If it prints jobs and a summary without errors, you're set up correctly. ✅

---

## 7. Open the web dashboard (the main way to use it)

```bash
./venv/bin/python -m webapp
```

Then open **<http://127.0.0.1:8000>** in the browser. You'll see Overview,
Manual Apply (with the LinkedIn / Naukri / Indeed platform tabs), Walk-ins,
Cold Mails, and Applied.

- Press **Ctrl+C** in the terminal to stop the dashboard.
- The dashboard has its own built-in scheduler. To make it auto-fetch while
  it's open, set this in `.env`:
  ```ini
  AUTO_FETCH=1
  AUTO_FETCH_TIMES=08:00,18:00
  ```
- Running on a different port (if 8000 is busy):
  ```bash
  WEBAPP_PORT=8800 ./venv/bin/python -m webapp
  ```

> Tip: make starting it one command. Add this to `~/.bashrc`:
> ```bash
> alias jobhunt='cd ~/job_automation && ./venv/bin/python -m webapp'
> ```
> Then just type `jobhunt` anytime.

---

## 8. (Optional) Telegram remote control

If you filled in the Telegram values, run the bot in a second terminal:

```bash
./venv/bin/python -m telegram_bot.bot
```

Then message your bot `/start` from your phone. It only replies to your own
`TELEGRAM_CHAT_ID`.

---

## Set the timezone (so schedules fire in IST)

```bash
sudo timedatectl set-timezone Asia/Kolkata
```

---

## Common problems

| Problem | Fix |
|---------|-----|
| `bash\r: No such file` or weird `\r` errors | Windows line endings. Run `sudo apt install -y dos2unix && dos2unix deploy/*.sh .env` |
| `ModuleNotFoundError` | You skipped step 3, or ran `python main.py` instead of `./venv/bin/python main.py`. |
| `python3: command not found` | Redo step 1. |
| Gmail auth error | Use an **App Password**, not your normal password, and enable 2-Step Verification first. |
| Dashboard won't open | Make sure the `python -m webapp` terminal is still running; use the exact URL `http://127.0.0.1:8000`. |
| No jobs found | Add Gmail job alerts (see the main [`README.md`](README.md)) or broaden `JOB_KEYWORDS` in `config.py`. |

For everything else — how sources work, the Excel tracker, safety rails, the full
feature list — see the main [`README.md`](README.md).
