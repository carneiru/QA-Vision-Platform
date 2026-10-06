# QA Vision — setup guide

Everything needed to run QA Vision, connect CI to it, and move it to a server. Three stages,
each building on the previous one:

| Stage | Where it runs | Who can send results | Guide |
|---|---|---|---|
| **1. Local** | your machine | only your machine (CLI) | sections 1–4 |
| **2. Pilot** | your machine + a tunnel | GitHub/GitLab hosted CI, while the tunnel is open | section 5 |
| **3. Production** | one VM with a domain | everyone, always | section 6 → [`deploy/README.md`](../deploy/README.md) |

Commands are given for **PowerShell** (Windows) unless marked; Git Bash/Linux/macOS work too.

---

## 1. Prerequisites

- **Docker Desktop** (Compose 2.24+): runs the whole platform.
- **Git**, to clone the repository.
- **Python 3.9+**, only to run the collector from your machine.
- Node.js is **not** needed: the dashboard is built inside Docker.

## 2. Run the platform

```powershell
git clone https://github.com/carneiru/QA-Vision-Platform.git
cd QA-Vision-Platform
& "C:\Program Files\Git\bin\bash.exe" deploy/init-env.sh localhost you@example.com   # writes .env
docker compose up -d --build --wait gateway
```

- Git Bash is called by its full path: a plain `bash` in PowerShell may start WSL instead.
  On Linux/macOS: `bash deploy/init-env.sh localhost you@example.com`.
- `init-env.sh` writes a git-ignored `.env` with `SECRET_KEY`, `INTERNAL_API_PASSWORD` and
  `POSTGRES_PASSWORD`. Compose reads it on every command; you never export secrets by hand.
- If port **8080** is taken on your machine, add `GATEWAY_HTTP_PORT=18080` to `.env`.
- First start takes a few minutes (image builds and database migrations).

Open **https://localhost:8443** and accept the self-signed certificate warning.

| Task | Command |
|---|---|
| Status | `docker compose ps` |
| Logs of one service | `docker compose logs -f auth-service` |
| Stop (keeps data) | `docker compose down` |
| Wipe all data | `docker compose down --volumes` |
| Update to the latest code | `git pull` then `docker compose up -d --build --wait gateway` |

Data lives in Docker volumes (`qa-vision_*`): it survives `down` and restarts, not `down --volumes`.

## 3. First account, organization and project

1. **Create account** on the sign-in page.
2. **Verify the email.** Without a mail server the link is written to the log:
   ```powershell
   docker compose logs auth-service | Select-String "Verification email"
   ```
   Open the `https://localhost:8443/verify-email?token=…` link: it signs you in. A link works
   **once** and expires after **24 hours**. To send real email, see `deploy/README.md` §5.
3. **Projects → New organization**, then **New project** under it. In the project's
   **Settings → Repositories**, paste the address of the repository your tests live in.
4. **Invite colleagues:** sidebar → **Organization** → invite by email → **Copy link** and send
   it to them; they open it after creating their own account.

> **Lost password:** sign-in page → **Forgot password?** Without SMTP the link is in the log:
> `docker compose logs auth-service | Select-String "Password reset email"`. It works **once**
> and expires after **30 minutes**; using it signs out every device. Signed in, change it
> under **Security → Password**. Google/Microsoft accounts have no password here.

## 4. Send test results from your machine (CLI)

1. **API key:** project → **Settings → API keys → Create key → Copy key.** The full key is
   shown **only once**; afterwards only its prefix is visible. Lost it? Create another and
   revoke the old one.
2. **Your tests must produce JUnit XML** (or TRX, NUnit 3, xUnit.net, TestNG, Cucumber JSON,
   Playwright JSON). Examples: `pytest --junitxml=reports/junit.xml`, Maven Surefire
   (`target/surefire-reports/*.xml`), Playwright (`PLAYWRIGHT_JUNIT_OUTPUT_NAME=reports/junit.xml npx playwright test --reporter=junit`,
   or its JSON reporter), `dotnet test --logger trx` (writes `TestResults/*.trx`).
3. **Upload**, from the folder holding the reports:
   ```powershell
   pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.3.0#subdirectory=collector"
   # the local stack's certificate is self-signed; run this in the QA-Vision-Platform folder
   docker compose cp gateway:/etc/nginx/certs/tls.crt $HOME\qav-ca.crt

   $env:QAV_URL = "https://localhost:8443"
   $env:QAV_API_KEY = "<your key>"
   qav-collector check "reports/**/*.xml" --ca-file $HOME\qav-ca.crt    # verifies everything, uploads nothing
   qav-collector upload "reports/**/*.xml" --ca-file $HOME\qav-ca.crt
   ```
   To keep test cases in sync from your `.feature` files, add a second CI step after the upload:
   `qav-collector import-features "tests/features/**/*.feature"`. It uses the same `QAV_API_KEY`
   and syncs only from `master` (set `QAV_IMPORT_BRANCH` to change that); see ADR-024.
4. The project's **Overview** shows the run, what failed and the pass rate. **Settings → Wire up
   your CI** always shows the right snippet for where the platform is running.

## 5. Pilot: hosted CI through a tunnel

Hosted CI runners (GitHub, GitLab) cannot reach `localhost`. A temporary tunnel gives the local
platform a public address. **Check your company's policy first**: a tunnel exposes your
machine to the internet while it is open.

1. **Open the tunnel** in a separate PowerShell window and keep it open:
   ```powershell
   & "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url https://localhost:8443 --no-tls-verify
   ```
   (Install `cloudflared` from Cloudflare's site if missing.) It prints an address like
   `https://random-words.trycloudflare.com`. Ctrl+C closes it.
2. **In the GitHub repository → Settings → Secrets and variables → Actions:**
   - secret `QAV_API_KEY` = the project's API key
   - variable `QAV_URL` = the tunnel address, without a trailing slash
3. **Add the upload step to the workflow**, after the tests (they must write JUnit XML):
   ```yaml
   - uses: carneiru/QA-Vision-Platform/collector-action@collector-v0.3.0
     if: always()                       # report failing builds too
     with:
       url: ${{ vars.QAV_URL }}
       patterns: "reports/**/*.xml"
     env:
       QAV_API_KEY: ${{ secrets.QAV_API_KEY }}
   ```
   For a change list per build, check out with `fetch-depth: 2`. This repository's own
   `.github/workflows/ci.yml` is a complete working example (one run per job).
4. **Push.** Each build appears in the project a minute later.

Pilot limits: the tunnel address **changes every time it restarts** (update `QAV_URL`), and
results sent while the tunnel or the laptop is down are lost; the builds themselves stay
green — the collector never fails a build because the platform is unreachable.

GitLab: `include:` the template in `templates/qav-collector.gitlab-ci.yml` and set `QAV_URL`
and a masked `QAV_API_KEY` as CI/CD variables. Jenkins: the shared library in
`collector-jenkins/` (`qavCollectorUpload` step). Azure Pipelines: add `QAV_API_KEY` as a
**secret** pipeline variable and map it in the step's `env:` (Azure gives secrets to scripts
only that way), or use the step template `templates/qav-collector.azure-pipelines.yml`;
Microsoft-hosted agents need a public `QAV_URL`, as with GitHub. The **Wire up your CI** card
shows every one of them with this deployment's address filled in.

## 6. Production

Move to a VM when a colleague starts depending on the data, a second CI system is connected,
or results become worth keeping. Follow **[`deploy/README.md`](../deploy/README.md)**: one Ubuntu
VM, a DNS record, three commands; certificates renew themselves and backups run daily.

Moving the pilot: back up the local database first if you want to keep it
(`docker compose exec -T postgres pg_dumpall -U postgres > qav-pilot.sql`) and restore it on
the VM (`deploy/README.md` §7). Then point every repository's `QAV_URL` at the new domain and
close the tunnel for good.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `port is already allocated` on 8080 | Another program uses it: `GATEWAY_HTTP_PORT=18080` in `.env`. |
| "Invalid or expired verification token" | Links work once and for 24 h. Already used: just sign in. Expired: register again. |
| No verification email | No mail server configured: take the link from `docker compose logs auth-service`. |
| Signed out after changing `.env` | `SECRET_KEY` changed; sign in again. API keys keep working. |
| Collector: certificate errors on localhost | Pass `--ca-file` with the gateway certificate (section 4). |
| `curl` on Windows fails on a valid certificate | Windows' TLS checks revocation, which local CAs don't publish: add `--ssl-no-revoke`. |
| GitHub build passes but nothing arrives | `QAV_URL` variable missing, or the tunnel was closed/restarted (new address). |
| Collector exits with code 2 | A configuration problem (URL, key, no matching files): `qav-collector check` names it. |
| `exec … no such file or directory` building a container | A shell script has Windows line endings; the repository's `.gitattributes` forces LF on commit, re-checkout the file. |
