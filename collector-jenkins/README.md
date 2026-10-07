# QEOS collector — Jenkins shared library

A [shared library](https://www.jenkins.io/doc/book/pipeline/shared-libraries/)
with one step, `qeosCollectorUpload`, that installs the pinned collector and
uploads test reports as one run.

## Install

A shared library's `vars/` must sit at the repository root, so point Jenkins
at this directory through a library-only checkout:

- **Option A (recommended):** copy `vars/qeosCollectorUpload.groovy` into the
  shared library your Jenkins already uses.
- **Option B:** mirror this directory to its own repository and register it
  under *Manage Jenkins → System → Global Pipeline Libraries* (name
  `qeos`, default version = a `collector-v*` tag).

## Use

```groovy
@Library('qeos') _

pipeline {
  agent any          // needs Python 3.9+ and git
  stages {
    stage('Test') { steps { sh 'pytest --junitxml=reports/junit.xml || true' } }
  }
  post {
    always {
      withCredentials([string(credentialsId: 'qeos-api-key', variable: 'QEOS_API_KEY')]) {
        withEnv(['QEOS_URL=https://qeos.example.com']) {
          qeosCollectorUpload(patterns: 'reports/**/*.xml', environment: 'ci')
        }
      }
    }
  }
}
```

Parameters (all optional): `patterns`, `environment`, `caFile`,
`failOnError`, `extraArgs` (e.g. `--component product-api@$SHA`), `ref`
(collector tag to install), `source` (full pip requirement override, e.g. an
internal mirror). The API key is only ever read from the `QEOS_API_KEY`
environment variable, so it stays out of the build log; Jenkins `BUILD_URL`,
`GIT_COMMIT` and `GIT_BRANCH` are picked up automatically by the collector's
CI detection.

## Renamed from `qavCollectorUpload`

The step was `qavCollectorUpload` before QEOS got its name, and the docs used the
credential id `qav-api-key`. `vars/qavCollectorUpload.groovy` is kept as a deprecated
wrapper that echoes one warning, then:

- with `ref: 'collector-v0.3.0'` or older (what the dashboard's snippet used to pass), or a
  `source` naming `qav-collector`, it behaves exactly as before: it installs `qav-collector`
  into `.qav-venv` and runs `python -m qav_collector`, so a Jenkinsfile that later runs
  `.qav-venv/bin/python -m qav_collector import-features …` keeps working unchanged;
- with any other `ref` (`collector-v0.4.0` or later, a branch, a SHA) or no `ref`, it calls
  `qeosCollectorUpload` with the same parameters, which installs `qeos-collector` into
  `.qeos-venv`. A pipeline that still binds the key as `QAV_API_KEY` keeps working, with a
  deprecation line from the collector. Moving to 0.4.0 also means changing an
  import-features line to `.qeos-venv/bin/python -m qeos_collector import-features …`.

Copy both files when you copy the library (Option A). Rename the Jenkins credential to
`qeos-api-key`, or keep its old id in your `withCredentials`.
