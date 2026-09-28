---
name: no-local-testing
description: "Never build/test LaserDriver locally (no local pytest, make, Docker); GitHub CI builds and generates the full Raspbian images"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 58e09057-b178-4015-b6fd-b60758325c6e
  modified: 2026-09-27T23:12:43.524Z
---

Never try to build or test the LaserDriver Pi software locally on the user's Mac: no local venvs, `make`, pytest runs, or starting Docker Desktop.

**Why:** The project uses GitHub CI (`.github/workflows/pi-deploy.yml`, on `main` since v0.1.0) to build, test, and generate full Raspbian images. To run it, push a `v*` tag (e.g. `v0.1.0-rcN`): tag pushes run the workflow at the tagged commit and publish a release with golden images. In one session, local testing needed a venv, and starting Docker Desktop left an admin-password prompt on the user's screen.

**How to apply:** Put new build and test steps into the CI workflow and packaging (`Pi/packaging/build-deb.sh`, `inject-laserhat.sh`) and let CI verify them. Say plainly that something has not been verified until CI has run.
