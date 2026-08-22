# Turning on LinkedIn posting (After Work)

This is a one-time setup. When you finish, the Viral agent can post to **your
own** LinkedIn profile automatically. It takes about 20 minutes, most of which
is LinkedIn's forms. You do not need to write any code.

Until you finish this, the agent still works -- it just stays in **dry run**
(it drafts and saves posts but does not publish). That is the safe default.

---

## Step 1 - Create a LinkedIn app

1. Go to https://developer.linkedin.com/ and click **Create app**.
2. Fill in the app name (e.g. "After Work Poster"), your LinkedIn page (any
   page you control, or create a simple one), and a logo. Submit.
3. Open your app, go to the **Auth** tab. Copy the **Client ID** and
   **Client Secret** -- you will paste them into `.env` in Step 3.
4. Still on the **Auth** tab, under **Authorized redirect URLs**, add exactly:
   ```
   http://localhost:8000/callback
   ```
   Save.

## Step 2 - Request the posting permission

1. Go to the **Products** tab of your app.
2. Request **"Share on LinkedIn"** and **"Sign In with LinkedIn using OpenID
   Connect"**. These are usually approved instantly.
   - "Share on LinkedIn" gives the `w_member_social` permission (posting).
   - "Sign In with OpenID Connect" gives `openid` + `profile` (so the helper
     can read your member id automatically).

## Step 3 - Put your app credentials in .env

1. If you have not already, copy `.env.example` to `.env`.
2. Fill in these lines with the values from Step 1:
   ```
   LINKEDIN_CLIENT_ID=...your client id...
   LINKEDIN_CLIENT_SECRET=...your client secret...
   LINKEDIN_REDIRECT_URI=http://localhost:8000/callback
   ```

## Step 4 - Get your token (the easy part)

Run:
```
python linkedin_auth.py
```
It will:
1. Open a LinkedIn page in your browser -- click **Allow**.
2. Catch the response automatically and print two lines that look like:
   ```
   LINKEDIN_ACCESS_TOKEN=AQV...long string...
   LINKEDIN_ACTOR_URN=urn:li:person:AbC123
   ```
3. Copy those two lines into your `.env` (replacing the empty ones).

## Step 5 - Test in dry run, then go live

1. Leave `LINKEDIN_DRY_RUN=true` and run:
   ```
   python -m agents.orchestrator "go viral about a topic you care about"
   ```
   Check the draft it prints and saves. Nothing is posted yet.
2. When you are happy, set `LINKEDIN_DRY_RUN=false` in `.env` and run it again.
   **Watch the first real post** before letting it run unattended.

---

## Step 6 - Publishing and scheduling from the dashboard

Open the dashboard (`run_app.bat`, or http://localhost:8510) and go to the
**Approval Queue** tab. Every LinkedIn item there gives you three choices:

- **Publish now** - posts it to your profile immediately.
- **Schedule** - pick a date and time and it goes out then, on its own.
- **Reject** - drop it.

Substack items only have **Mark as done**, because Substack has no API. You
still paste those in yourself; marking them done is what keeps next week's
pillar balance honest.

### The safety switch

The sidebar shows **DRY RUN** or **LIVE**.

- **DRY RUN** (the default): nothing ever reaches LinkedIn. Publishing is
  simulated, and scheduled posts just sit there - they are *not* used up, so
  anything you scheduled still goes out later when you switch to live.
- **LIVE**: real posts. Turning it on takes a second confirming click, and
  each individual "Publish now" needs its own tick-box first. That is
  deliberate - a public post cannot be undone from code.

### How scheduling actually works

LinkedIn's API cannot hold a post for later, so your PC does it. Run
`setup_publish_task.bat` **once** (double-click it). That tells Windows to
check every 10 minutes for anything due, quietly in the background - no
console window, and it keeps working after a restart.

What that means in practice:

- A post scheduled for 8am goes out at 8am **even if the dashboard is closed**,
  as long as your PC is on and connected.
- If your PC is asleep or offline at 8am, it goes out at the next check after
  it wakes.
- Anything more than 12 hours overdue is **not** posted. It is marked "missed"
  and shows under *Needs attention*, so coming back from a weekend away never
  fires a pile of stale posts at once. Reschedule it if you still want it.

Check it is running: `logs\publish_last_status.txt` holds a one-line OK/FAILED
from the last check. `logs\publish_due.log` has the full history. To turn the
whole thing off, double-click `remove_publish_task.bat`.

---

### Notes
- The access token lasts about 60 days. When posting starts failing with an
  auth error, just run `python linkedin_auth.py` again to get a fresh one.
  A failed scheduled post is recorded under *Needs attention* in the Approval
  Queue rather than lost, and `logs\publish_last_status.txt` will say FAILED.
- Your Substack Notes are never auto-posted (Substack has no API); the agent
  saves them to `Substack Notes.docx` for you to paste in yourself.
- Never commit `.env` -- it holds your secret. It is already gitignored.
