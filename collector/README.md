# qav-collector

Uploads JUnit XML test results from a CI job to the QA Vision platform. Standard library only,
Python 3.9 or newer, nothing else to install.

## Install

```bash
pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.2.0#subdirectory=collector"
```

## Use

Create an API key for the project in the platform, store it as a CI secret named `QAV_API_KEY`,
and run the collector after the tests — also when they fail:

```bash
export QAV_URL=https://qav.example.com
qav-collector upload "reports/**/*.xml"
```

All matching files become **one run**. On GitHub Actions, GitLab CI, Jenkins and Azure Pipelines the commit, branch
and job URL are detected automatically. If an upload is retried after the platform stored it but
the answer was lost, the collector's Idempotency-Key makes the platform return the stored run
instead of storing it twice.

### GitHub Actions

```yaml
      - name: Run tests
        run: pytest --junitxml=reports/junit.xml

      - name: Upload results to QA Vision
        if: always()
        env:
          QAV_URL: https://qav.example.com
          QAV_API_KEY: ${{ secrets.QAV_API_KEY }}
        run: |
          pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.2.0#subdirectory=collector"
          qav-collector upload "reports/**/*.xml"
```

### GitLab CI

```yaml
test:
  script:
    - pytest --junitxml=reports/junit.xml
  after_script:
    - pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.2.0#subdirectory=collector"
    - qav-collector upload "reports/**/*.xml"
  variables:
    QAV_URL: https://qav.example.com
  # QAV_API_KEY: a masked CI/CD variable in the project settings
```

### Jenkins

```groovy
post {
  always {
    withCredentials([string(credentialsId: 'qav-api-key', variable: 'QAV_API_KEY')]) {
      sh '''
        pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.2.0#subdirectory=collector"
        QAV_URL=https://qav.example.com qav-collector upload "target/surefire-reports/*.xml"
      '''
    }
  }
}
```

### Azure Pipelines

```yaml
steps:
  - script: mvn test   # or pytest --junitxml=reports/junit.xml, dotnet test --logger trx, …
  - script: |
      pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.2.0#subdirectory=collector"
      qav-collector upload "**/TEST-*.xml"
    displayName: Upload test results to QA Vision
    condition: always()        # report results even when the tests failed
    continueOnError: true      # a failed upload does not fail the pipeline
    env:
      QAV_URL: https://qav.example.com
      QAV_API_KEY: $(QAV_API_KEY)   # a secret variable reaches scripts only when mapped like this
```

Commit, branch (the source branch on a pull request), PR number, target branch and the build URL
are detected from `TF_BUILD` and the `BUILD_*` / `SYSTEM_*` variables; a retried job
(`System.JobAttempt`) is a new run. Reusable step template: `templates/qav-collector.azure-pipelines.yml`.
Hosted agents cannot reach a platform on `localhost`: use a self-hosted agent on that network or
a deployment with a public address.

### See what would be sent

```bash
qav-collector upload "reports/**/*.xml" --dry-run
```

prints the JSON and uploads nothing; no URL or key is needed.

## Options

Each option can also be set with the environment variable next to it. A flag wins over the
variable, and both win over what is detected from the CI system.

| Option | Variable | Meaning |
|---|---|---|
| `--url` | `QAV_URL` | Platform URL (required unless `--dry-run`) |
| — | `QAV_API_KEY` | The project's API key. Environment only, never a flag |
| `--ci-provider` | `QAV_CI_PROVIDER` | `github_actions`, `gitlab_ci`, `jenkins`, `other` or `local` |
| `--branch` | `QAV_BRANCH` | Branch name |
| `--commit` | `QAV_COMMIT` | Commit SHA (7 to 40 hex characters; anything else is left out) |
| `--ci-run-url` | `QAV_CI_RUN_URL` | Link to the CI job |
| `--environment` | `QAV_ENVIRONMENT` | e.g. `staging` |
| `--idempotency-key` | `QAV_IDEMPOTENCY_KEY` | Overrides the key derived from the CI job |
| `--ca-file` | `QAV_CA_FILE` | Extra CA certificate to trust (a private CA, or the local stack's self-signed one) |
| `--component` | `QAV_COMPONENTS` | `NAME@SHA` of a repo/version this run exercised, e.g. the product build an E2E suite ran against. Flag repeatable; variable comma-separated. Up to 20 |
| `--client-cert` | `QAV_CLIENT_CERT` | Client certificate for mTLS, presented when the server asks for one |
| `--client-key` | `QAV_CLIENT_KEY` | Private key belonging to `--client-cert` |
| `--fail-on-error` | `QAV_FAIL_ON_ERROR=1` | Exit 1 if the upload fails |
| `--gate` | `QAV_GATE=1` | Exit 1 if the run has failures outside quarantine, or could not be uploaded (see below) |
| `--spool` | `QAV_SPOOL` | Directory keeping parts a failed upload could not deliver; the next invocation resends them first, under their original Idempotency-Key (so nothing is ever stored twice). Capped at 100 files; rejected uploads (401/409) are never spooled. Point it at a persistent runner path — a wiped workspace wipes the spool |
| `--dry-run` | — | Print the JSON; upload nothing |

## `qav-collector check`

Verifies the setup without uploading — run it once when wiring a new pipeline:

```
qav-collector check "reports/**/*.xml" --url https://qa-vision.example.com
```

It checks, in order: the URL shape, the TLS trust (`--ca-file` honoured), the
API key (a `GET /api/v1/collect/key` names the project it belongs to), and —
when patterns are given — that report files match and parse. Exits 2 on the
first failed check, 0 when everything passes.

## `.qav.yml`

Project defaults, read from the working directory — flags beat environment
variables beat the file. Flat keys and string lists only (a built-in reader,
no YAML dependency); the API key is never accepted here:

```yaml
url: https://qa-vision.example.com
environment: staging
ca-file: certs/internal-ca.pem
spool: .qav-spool
fail-on-error: true
patterns:
  - "reports/**/*.xml"
components:
  - product-api@a1b2c3d4e5f6
```

## CODEOWNERS

When the working directory has a `CODEOWNERS` file (root, `.github/` or
`docs/`), every result whose `file` matches a pattern carries its owners
(git semantics: last matching line wins). Shown on the run detail view —
a failing test names the team that owns it.

## Exit codes

| Code | When |
|---|---|
| 0 | Uploaded; nothing to upload; or the upload failed and neither `--fail-on-error` nor `--gate` is set |
| 1 | The upload failed and `--fail-on-error` or `--gate` is set; or `--gate` found failures outside quarantine |
| 2 | A usage or configuration error: no URL or key, no file matched, an `http://` URL that is not localhost, an unusable `--ca-file` |

By default an unreachable platform never turns a build red; a misconfigured collector always does.

## Gating on quarantine (`--gate`)

Quarantine a flaky test in the dashboard (Flaky view → Quarantine) and it keeps running and
showing up, but its failures stop counting. With `--gate`, the collector decides the build:

- It exits 1 when the run has failures outside quarantine, and 0 when every failure is
  quarantined.
- It fails closed: an upload that did not happen exits 1, because nothing was checked.
- The test step itself must not fail the job, so the collector can decide. In GitHub Actions use
  `continue-on-error: true` on the test step; in Azure Pipelines use `continueOnError: true`; in
  GitLab use `allow_failure: true` on the test command's job, or `|| true`.
- Older platforms that do not report quarantine count every failure.

## What it does with the files

- Reads `<testsuites>`/`<testsuite>` reports: pytest, Maven Surefire, Playwright, cucumber-js and
  anything else that writes JUnit XML. A test's status is `errored` if it has an `<error>`,
  else `failed` for `<failure>`, else `skipped` for `<skipped>`, else `passed`. Surefire's
  `flakyFailure`/`rerunFailure` elements become per-attempt results, so flaky tests show up
  as pass+fail within one run.
- Also reads, detected by the root element: .NET TRX (`<TestRun>`, vstest/`dotnet test`),
  NUnit 3 (`<test-run>`), xUnit.net v2 (`<assemblies>`) and TestNG (`<testng-results>`).
  Formats mix freely in one upload; every file lands in the same run.
- Cucumber JSON (the classic formatter of cucumber-jvm/js/rb): each scenario becomes one
  result (feature name as suite, feature uri as class), background steps count into their
  scenario, a failed step fails the scenario, and undefined/pending steps leave it skipped.
- Playwright's JSON reporter (`--reporter=json`): every retry attempt is kept as its own
  result (a flaky spec shows as fail+pass in one run), project name as suite, spec file as
  class, `timedOut` counts as failed and `interrupted` as errored.
- Skips, with a warning, files over 50 MB, files that are not well-formed XML, and files that
  declare a DOCTYPE or entities (JUnit never needs one; refusing them blocks XML entity attacks).
- Cuts failure messages and output to 64 KB, as the platform does.
- More than 20,000 results (or 9 MB) are sent as several runs, `part 1 of N` and so on.

## Network and security

- HTTPS is required, except for `http://localhost`, `127.0.0.1` and `::1`.
- Certificates are always verified; there is no option to turn that off. Use `--ca-file` for a
  private CA.
- `HTTPS_PROXY` and `NO_PROXY` are honoured.
- Redirects are not followed, so the key is never sent anywhere but `QAV_URL`.
- Retries: connection errors, timeouts and 5xx answers are retried after 1, 2, 4 and 8 seconds;
  429 waits for `Retry-After` (at most 10 s). At most 5 attempts and 2 minutes per run.
- The API key is never printed.

## Develop

```bash
cd collector
uv venv --seed --python 3.9 .venv
.venv/Scripts/python -m pip install -e . pytest    # .venv/bin/python on Linux/macOS
.venv/Scripts/python -m pytest -q
```

A release is a git tag `collector-v<version>` on this repository, matching `__version__` in
`src/qav_collector/__init__.py`.
