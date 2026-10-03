# QA Vision collector — Jenkins shared library

A [shared library](https://www.jenkins.io/doc/book/pipeline/shared-libraries/)
with one step, `qavCollectorUpload`, that installs the pinned collector and
uploads test reports as one run.

## Install

A shared library's `vars/` must sit at the repository root, so point Jenkins
at this directory through a library-only checkout:

- **Option A (recommended):** copy `vars/qavCollectorUpload.groovy` into the
  shared library your Jenkins already uses.
- **Option B:** mirror this directory to its own repository and register it
  under *Manage Jenkins → System → Global Pipeline Libraries* (name
  `qa-vision`, default version = a `collector-v*` tag).

## Use

```groovy
@Library('qa-vision') _

pipeline {
  agent any          // needs Python 3.9+ and git
  stages {
    stage('Test') { steps { sh 'pytest --junitxml=reports/junit.xml || true' } }
  }
  post {
    always {
      withCredentials([string(credentialsId: 'qav-api-key', variable: 'QAV_API_KEY')]) {
        withEnv(['QAV_URL=https://qa-vision.example.com']) {
          qavCollectorUpload(patterns: 'reports/**/*.xml', environment: 'ci')
        }
      }
    }
  }
}
```

Parameters (all optional): `patterns`, `environment`, `caFile`,
`failOnError`, `extraArgs` (e.g. `--component product-api@$SHA`), `ref`
(collector tag to install), `source` (full pip requirement override, e.g. an
internal mirror). The API key is only ever read from the `QAV_API_KEY`
environment variable, so it stays out of the build log; Jenkins `BUILD_URL`,
`GIT_COMMIT` and `GIT_BRANCH` are picked up automatically by the collector's
CI detection.
