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
2. When you are happy, go live. Two ways:
   - **In the dashboard (easiest):** open `streamlit run app.py` and flip the
     **"Post to LinkedIn for real"** toggle in the left sidebar to ON. It turns
     posting on for that session -- no file editing, no restart. The sidebar
     warns you it is live, and warns if your token is missing.
   - **Permanently:** set `LINKEDIN_DRY_RUN=false` in `.env`. That makes LIVE the
     startup default every time (the toggle still overrides it per session).
   **Watch the first real post** before letting it run unattended.

---

### Notes
- The access token lasts about 60 days. When posting starts failing with an
  auth error, just run `python linkedin_auth.py` again to get a fresh one.
- Your Substack Notes are never auto-posted (Substack has no API); the agent
  saves them to `Substack Notes.docx` for you to paste in yourself.
- Never commit `.env` -- it holds your secret. It is already gitignored.
