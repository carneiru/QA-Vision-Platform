# Deploying QEOS on one VM

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
- **A domain name** you can add a DNS record to, e.g. `qeos.example.com`.
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

## 4. Install QEOS

```bash
git clone https://github.com/carneiru/QA-Vision-Platform.git
cd QA-Vision-Platform
bash deploy/init-env.sh qeos.example.com ops@example.com
```

`init-env.sh` writes `.env` (mode 600, git-ignored) with the domain and freshly generated
secrets: `SECRET_KEY`, `INTERNAL_API_PASSWORD`, `POSTGRES_PASSWORD`, `TM_SECRETS_KEY`. It refuses to overwrite
an existing `.env`. **Back this file up somewhere safe**: losing it means losing access to
the database. Include it in every `.env` backup: `TM_SECRETS_KEY` encrypts the GitHub tokens used to
run tests from QEOS, and losing it means re-entering each project's GitHub token.

Then start everything:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait edge
```

The first start takes a few minutes (image builds, migrations, certificate issuance).
Open `https://qeos.example.com`, create the first account, organization and project.

> Tip: put `alias qeos='docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml'`
> in `~/.bashrc`; the commands below then shorten to `qeos ps`, `qeos logs -f gateway`, …

## 5. Email

Without SMTP settings the platform still works: verification and password-reset links are
written to the auth-service log (`qeos logs auth-service | grep "Verification email"`), and
email notification channels report "SMTP is not configured". To send real email, add to `.env`
and recreate the services that send mail (`qeos up -d auth-service ingestion-service weekly-summary`).
Compose passes these variables to all three:

```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=…
SMTP_PASSWORD=…
EMAILS_FROM_EMAIL=qeos@example.com
# optional: SMTP_TLS=false for a relay without STARTTLS; EMAILS_FROM_NAME=QEOS
```

## 6. Connect CI

In each repository that reports to QEOS:

- secret `QEOS_API_KEY`: a key from the project's **Settings → API keys**
- variable or env `QEOS_URL`: `https://qeos.example.com`

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
a backup on the same disk does not survive the disk. Settings: `QEOS_BACKUP_DIR`,
`QEOS_BACKUP_KEEP_DAYS`.

**Restore** (onto a fresh install with the same `.env`):

```bash
qeos up -d --wait postgres
gunzip -c backups/qeos-<timestamp>.sql.gz | qeos exec -T postgres psql -U postgres
qeos up -d --build --wait edge
```

One `ERROR: role "postgres" already exists` during the restore is expected and harmless.

## 8. Updates

```bash
cd QA-Vision-Platform
bash deploy/backup.sh          # always before an update
git pull
qeos up -d --build --wait edge
```

Database migrations run automatically on every start.

**Existing installs and `TM_SECRETS_KEY`.** `init-env.sh` never overwrites an existing `.env`, so an install
made before "Run from QEOS" has no `TM_SECRETS_KEY`. Add it once, by hand, then restart:

```bash
# either (needs only openssl)
echo "TM_SECRETS_KEY=$(openssl rand -base64 32 | tr '+/' '-_')" >> .env
# or (needs the cryptography package)
python3 -c "from cryptography.fernet import Fernet; print('TM_SECRETS_KEY=' + Fernet.generate_key().decode())" >> .env
qeos up -d --wait edge
```

Without the key everything else works, but Project Settings shows "Running tests from QEOS is not
configured on this server" and Play stays disabled. Keep the key in your `.env` backups: changing or losing
it makes stored GitHub tokens unreadable, and owners then save them again in Settings.

### Upgrading from QA Vision names

The platform was called QA Vision before it became QEOS. An install from before the rename keeps
working after `git pull`; only these settings change name:

- **`.env`:** rename `QAV_DOMAIN` to `QEOS_DOMAIN` (compose stops with "set QEOS_DOMAIN" until you
  do). If `EMAILS_FROM_NAME=QA Vision` is set, change it to `QEOS`. `TM_SECRETS_KEY` and every
  other variable keep their names. `deploy/backup.sh` still reads `QAV_BACKUP_DIR` and
  `QAV_BACKUP_KEEP_DAYS` when the `QEOS_*` names are not set, and old `qav-*.sql.gz` dumps age
  out with the new ones.
- **CI:** the collector reads `QEOS_URL` and `QEOS_API_KEY`. The `QAV_*` names still work, with
  a one-line deprecation warning, and so does the `qav-collector` command (see `collector/README.md`).
- **What keeps working unchanged:** API keys that start with `qav_` (new keys start with `qeos_`),
  and signed-in browsers: the old `qav_refresh` cookie is accepted once and replaced by
  `qeos_refresh`, so nobody is logged out.
- **Data:** the Docker volumes keep their physical names (`qa-vision_qav_postgres_data`,
  `qa-vision_qav_gateway_certs`, `qa-vision_qav_caddy_data`, `qa-vision_qav_caddy_config`) and
  the compose project is still `qa-vision`, so no data moves. If Compose ever asks to recreate a
  volume, answer N.

## 9. Security notes

- Only Caddy publishes ports. The gateway trusts `X-Forwarded-For` from Caddy's fixed
  address alone, so per-IP rate limits (login: 5 requests/s) apply to each real client.
- Caddy sends `Strict-Transport-Security`, and renews the certificate on its own.
- `.env` holds every secret. Changing `SECRET_KEY` signs everyone out; API keys keep working.
- Keep the OS patched: `sudo apt-get upgrade` monthly, or enable unattended upgrades.
