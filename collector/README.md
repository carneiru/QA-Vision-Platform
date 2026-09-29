# qav-collector

Uploads JUnit XML test results from a CI job to the QA Vision platform. Standard library only,
Python 3.9 or newer, nothing else to install.

## Install

```bash
pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.1.0#subdirectory=collector"
```

## Use

Create an API key for the project in the platform, store it as a CI secret named `QAV_API_KEY`,
and run the collector after the tests — also when they fail:

```bash
export QAV_URL=https://qav.example.com
qav-collector upload "reports/**/*.xml"
```

All matching files become **one run**. On GitHub Actions, GitLab CI and Jenkins the commit, branch
and job URL are detected automatically, and a re-run of the same job replays the run it already
stored instead of storing it twice.

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
          pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.1.0#subdirectory=collector"
          qav-collector upload "reports/**/*.xml"
```

### GitLab CI

```yaml
test:
  script:
    - pytest --junitxml=reports/junit.xml
  after_script:
    - pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.1.0#subdirectory=collector"
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
        pip install "qav-collector @ git+https://github.com/carneiru/QA-Vision-Platform@collector-v0.1.0#subdirectory=collector"
        QAV_URL=https://qav.example.com qav-collector upload "target/surefire-reports/*.xml"
      '''
    }
  }
}
```

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
| `--fail-on-error` | `QAV_FAIL_ON_ERROR=1` | Exit 1 if the upload fails |
| `--dry-run` | — | Print the JSON; upload nothing |

## Exit codes

| Code | When |
|---|---|
| 0 | Uploaded; nothing to upload; or the upload failed and `--fail-on-error` is not set |
| 1 | The upload failed and `--fail-on-error` is set |
| 2 | A usage or configuration error: no URL or key, no file matched, an `http://` URL that is not localhost, an unusable `--ca-file` |

By default an unreachable platform never turns a build red; a misconfigured collector always does.

## What it does with the files

- Reads `<testsuites>`/`<testsuite>` reports: pytest, Maven Surefire, Playwright, cucumber-js and
  anything else that writes JUnit XML. A test's status is `errored` if it has an `<error>`,
  else `failed` for `<failure>`, else `skipped` for `<skipped>`, else `passed`. Surefire's
  `flakyFailure`/`rerunFailure` elements are earlier attempts and are ignored.
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
