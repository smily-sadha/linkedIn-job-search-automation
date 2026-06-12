# Running the Job-Hunt Assistant on a Raspberry Pi (24/7)

Goal: the Pi runs the bot **every 3 hours, all day, even when your laptop is
off**. Linux's built-in scheduler (`cron`) does the triggering — you set it up
once and forget it.

> You'll type commands in the Pi's terminal. If your Pi has a screen+keyboard,
> open **Terminal**. If it's "headless", connect from your laptop with
> `ssh pi@<pi-ip-address>` (find the IP in your router, or run `hostname -I` on
> the Pi).

---

## Step 0 — One-time Pi basics

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
sudo timedatectl set-timezone Asia/Kolkata     # so 9am means 9am IST
```

## Step 1 — Get the project onto the Pi

Copy the **whole project folder** to the Pi — but **NOT the `venv/` folder**
(the Windows venv won't work on the Pi; we rebuild it there).

Pick whichever is easiest:

**A) USB stick** — copy the folder, then on the Pi move it to your home dir, e.g.
`/home/pi/job_automation`.

**B) From your laptop over the network** (run on your *laptop*, PowerShell):
```powershell
scp -r "d:\D\main copy\job search autiomation" pi@<pi-ip>:/home/pi/job_automation
```
(If `venv` got copied, just delete it on the Pi: `rm -rf /home/pi/job_automation/venv`.)

You should end up with: `/home/pi/job_automation/` containing `main.py`,
`requirements.txt`, `config/`, `sources/`, etc.

## Step 2 — Copy your secrets + resume

These hold private info, so they're not in git. Make sure the Pi has:
- `.env`  (your Gmail App Password, Telegram token, chat id)
- `config/resumes/your-resume.pdf`

If you used `scp` above they came along. Double-check on the Pi:
```bash
cd /home/pi/job_automation
ls .env config/resumes/
```

## Step 3 — Run the setup script

This builds the Python environment, installs everything, and schedules the
3-hourly runs + weekly report automatically:

```bash
cd /home/pi/job_automation
bash deploy/setup_pi.sh
```

When it finishes you'll see the installed cron lines. That's it — **the bot is
now running automatically every 3 hours.**

> If you see an error like `bash\r: No such file` (Windows line endings), run:
> `sudo apt install -y dos2unix && dos2unix deploy/*.sh` then re-run Step 3.

## Step 4 — Test it once, by hand

```bash
./venv/bin/python main.py            # do one run now
./venv/bin/python main.py --status   # see the tracker summary
```
You should get a Telegram message and see jobs land in the tracker.

## Step 5 (optional) — Phone control 24/7

To use the Telegram bot anytime (`/status`, `/run`, `/manual`), run it as a
background service. First edit the paths in `deploy/jobhunt-bot.service` if your
folder/user differ from `/home/pi/job_automation` and `pi`, then:

```bash
sudo cp deploy/jobhunt-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jobhunt-bot
systemctl status jobhunt-bot          # should say "active (running)"
```

---

## Everyday use

- **Nothing to do** — it runs on its own. Open `tracker/job_applications.xlsx`
  (copy it to your laptop, or browse it on the Pi) to see new jobs in
  *Manual Apply Needed*, then apply on LinkedIn yourself.
- **Watch the logs:** `tail -f logs/scheduler.log`
- **See/Change the schedule:** `crontab -l` (list), `crontab -e` (edit).
  `0 */3 * * *` = every 3 hours. Change to `0 */6 * * *` for every 6 hours, etc.
  (If you widen the interval, also raise `lookback_hours` in `config/config.py`
  so no alert email is missed.)
- **Update the resume:** replace the PDF on the Pi; the bot rebuilds your skill
  profile automatically on the next run.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3: not found` | `sudo apt install -y python3 python3-venv python3-pip` |
| `bash\r` / line-ending errors | `dos2unix deploy/*.sh` |
| Cron not running | `grep CRON /var/log/syslog` to see cron activity |
| Gmail/Telegram fails | check `.env` was copied to the Pi correctly |
| Wrong run times | set timezone: `sudo timedatectl set-timezone Asia/Kolkata` |
