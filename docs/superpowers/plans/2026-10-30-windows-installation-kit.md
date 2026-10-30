# Windows installation kit implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline.

**Goal:** Provide actual installers in a folder and one documented installation command, alongside the published project.

**Architecture:** Track a pinned download manifest and PowerShell scripts in `installation/`. Cache verified installers in ignored `installation/packages/`. Build a separate ZIP from `git archive` plus those installers, excluding local data and credentials. The installer prepares a fresh local Windows environment and initial setup account; Google import remains an explicit UI action.

**Tech Stack:** Windows x64, PowerShell 5.1+, Git 2.51.2, Python 3.13.12, Node 22.20.0, uv 0.10.6, PostgreSQL 17.11.

**Spec:** User requested actual installer files in a folder and the command to install them. The selected data path is a fresh database and Google import, without a database dump. This kit includes tool installers; locked Python/npm dependencies still require Internet access on first installation.

## Constraints

- Pin official artifact URLs and SHA-256 values.
- Keep large installer binaries and generated distribution ZIPs out of Git history.
- Do not run system installers or initialize a database in the active project while verifying.
- Refuse fresh installation over an existing project database.
- Provide a nonmutating `-CheckOnly` mode and preserve already compatible tools.
- Do not launch duplicate web servers or import Google data automatically.

## Tasks

- [x] Add manifest, download/verify script and installation script.
- [x] Download all five packages into the installer folder and verify hashes.
- [x] Check PowerShell syntax and nonmutating mode.
- [x] Exercise dependency preparation, migrations, seed commands and bootstrap in a separate disposable workspace/database, then stop its PostgreSQL.
- [ ] Update deployment instructions, commit, fast-forward master and push.
- [ ] Build ZIP from the committed source plus installer packages and report its path and exact command.

## Verification

PowerShell syntax and `Install.ps1 -CheckOnly` passed. Five actual packages are present (164.7 MiB) with matching pinned SHA-256 values. A separate source workspace on PostgreSQL port 55433 completed dependency installation, all migrations, catalogue seeding, bootstrap and production frontend build. It contains setup, 11 employees, four issue methods and zero expertises. Its PostgreSQL was stopped afterwards. The existing-database guard was checked against the active checkout and refused initialization before modifications. System Git, Node and Python were already compatible on this machine, so the system-level EXE/MSI installation branches were not executed during the isolated check.
