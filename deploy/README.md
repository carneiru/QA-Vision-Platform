# Deploying QA Vision on one VM

The whole platform runs on a single Linux VM with the same Docker Compose stack used in
development, plus one extra service: **Caddy**, which obtains and renews a Let's Encrypt
certificate and is the only thing exposed to the internet. Kubernetes enters only when the
first multi-node deployment does (see the blueprint's adoption triggers).

```
internet ──443──▶ edge (Caddy, Let's Encrypt) ──▶ gateway (NGINX) ──▶ services ──▶ PostgreSQL
                  the only published ports         rate limits, routing    not reachable from outside
```

## 1. What you need

- **A VM**: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 30 GB disk is enough for a pilot
  (Azure `B2s`, AWS `t3.medium` or similar).
- **A domain name** you can add a DNS record to, e.g. `qa-vision.example.com`.
- **An email address** for Let's Encrypt certificate-expiry notices.

## 2. Network

1. Create a DNS **A record** for the domain pointing at the VM's public IP.
2. Firewall / network security group, inbound:
   - `443/tcp` from anywhere (the platform)
   - `80/tcp` from anywhere (Let's Encrypt validation and the HTTP→HTTPS redirect)
   - `22/tcp` from your own IP only (SSH)

   Nothing else: PostgreSQL and the services are never published.

## 3. Install Docker

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"   # log out and back in afterwards
docker compose version            # 2.24 or newer
```

## 4. Install QA Vision

```bash
git clone https://github.com/carneiru/QA-Vision-Platform.git
cd QA-Vision-Platform
bash deploy/init-env.sh qa-vision.example.com ops@example.com
```

`init-env.sh` writes `.env` (mode 600, git-ignored) with the domain and freshly generated
secrets: `SECRET_KEY`, `INTERNAL_API_PASSWORD`, `POSTGRES_PASSWORD`. It refuses to overwrite
an existing `.env`. **Back this file up somewhere safe**: losing it means losing access to
the database.

Then start everything:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait edge
```

The first start takes a few minutes (image builds, migrations, certificate issuance).
Open `https://qa-vision.example.com`, create the first account, organization and project.

> Tip: put `alias qav='docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml'`
> in `~/.bashrc`; the commands below then shorten to `qav ps`, `qav logs -f gateway`, …

## 5. Email

Without SMTP settings the platform still works: verification links are written to the
auth-service log (`qav logs auth-service | grep "Verification email"`). To send real email,
add to `.env` and restart `auth-service`:

```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=…
SMTP_PASSWORD=…
EMAILS_FROM_EMAIL=qa-vision@example.com
```

## 6. Connect CI

In each repository that reports to QA Vision:

- secret `QAV_API_KEY`: a key from the project's **Settings → API keys**
- variable or env `QAV_URL`: `https://qa-vision.example.com`

The **Settings → Wire up your CI** card shows the ready-to-paste snippet for GitHub
Actions, GitLab CI, Jenkins or the plain CLI, with this address filled in. No `--ca-file`
is needed: the certificate is a real one.

## 7. Backups

`deploy/backup.sh` dumps every database (one compressed file) and keeps 14 days.
Schedule it daily:

```bash
crontab -e
# 03:15 every day
15 3 * * * cd /home/<you>/QA-Vision-Platform && bash deploy/backup.sh >> backups/backup.log 2>&1
```

Copy the `backups/` directory off the VM regularly (object storage, another machine):
a backup on the same disk does not survive the disk. Settings: `QAV_BACKUP_DIR`,
`QAV_BACKUP_KEEP_DAYS`.

**Restore** (onto a fresh install with the same `.env`):

```bash
qav up -d --wait postgres
gunzip -c backups/qav-<timestamp>.sql.gz | qav exec -T postgres psql -U postgres
qav up -d --build --wait edge
```

One `ERROR: role "postgres" already exists` during the restore is expected and harmless.

## 8. Updates

```bash
cd QA-Vision-Platform
bash deploy/backup.sh          # always before an update
git pull
qav up -d --build --wait edge
```

Database migrations run automatically on every start.

## 9. Security notes

- Only Caddy publishes ports. The gateway trusts `X-Forwarded-For` from Caddy's fixed
  address alone, so per-IP rate limits (login: 5 requests/s) apply to each real client.
- Caddy sends `Strict-Transport-Security`, and renews the certificate on its own.
- `.env` holds every secret. Changing `SECRET_KEY` signs everyone out; API keys keep working.
- Keep the OS patched: `sudo apt-get upgrade` monthly, or enable unattended upgrades.
