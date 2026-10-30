# Offline Windows installation implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline.

**Goal:** Install the entire existing Windows x64 project from the ZIP without Internet access or pre-existing dependency caches.

**Architecture:** Prepare Python wheels from the locked requirements and an isolated npm content cache on a connected build machine. Bind asset hashes to normalized backend/frontend lock-file hashes. The installed kit verifies local files, uses uv with offline/no-index flags and npm with offline/ignore-scripts flags, and never invokes the downloader. Build includes only manifest-listed offline assets.

**Tech Stack:** Existing Windows PowerShell installer, Python 3.13, uv, npm/Node x64, PostgreSQL.

**Spec:** The owner explicitly requested a fully offline installation after the previous kit still downloaded Python/npm dependencies. Preserve the single Install.ps1 command, fresh-database guard and subsequent manual Google/XLSX import. No application or working-data changes.

## Constraints and review focus

- Missing, changed or stale assets fail before tools, environment or database initialization.
- Ignore global dependency caches during the isolated smoke test; use unreachable proxies and explicit offline options.
- npm lifecycle scripts must not trigger independent downloads; the complete frontend build must still work.
- Normalize lock-file line endings so a Git ZIP and Windows checkout share the same dependency identity.
- Do not run npm ci in the active frontend or modify the working virtual environment.
- Keep binary caches ignored by Git; retain manifest-based distribution contents.

## Tasks

- [x] Add asset validator and online preparation script, download all locked wheels and npm dependencies in isolated work directories.
- [x] Make Install.ps1 offline by default and include verified dependencies in Build-Bundle.ps1.
- [x] Check missing/corrupt/stale asset rejection before initialization and check PowerShell syntax.
- [x] Run a fresh isolated installation with empty user caches, offline flags and unreachable external proxies; check database/bootstrap and frontend build, then stop its PostgreSQL.
- [x] Update instructions and implement offline archive generation. Commit/push and final archive inspection follow these checks; their results are reported with the deliverable.

## Verification

Six asset validation checks passed. The default installer rejected a missing wheel before creating the virtual environment or PostgreSQL data directory. A complete isolated installation passed with HTTP/HTTPS/ALL proxies set to unreachable 127.0.0.1:9, empty external uv/npm caches and explicit offline flags. It installed 16 Python distributions and 156 npm packages, migrated a separate PostgreSQL on 55433, created setup with a valid initial password, 11 employees, four issue methods and zero expertises. Production frontend build and Django check passed. Post-install CheckOnly still validated all 317 source dependency files, demonstrating the bundled cache was not modified. The separate PostgreSQL was stopped and listener absence verified. Compatible host Git/Python/Node were reused; this was not a test of installing those EXE/MSI packages on a separate clean Windows OS.
