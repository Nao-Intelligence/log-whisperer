# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.3] - 2026-02-10

### Changed

- Chore contribution template ([#5](https://github.com/Nao-Intelligence/log-whisperer/pull/5))

## [0.2.2] - 2026-02-10

### Changed

- Chore contribution template ([#4](https://github.com/Nao-Intelligence/log-whisperer/pull/4))

## [0.2.0] - 2026-02-09

### Added
- Notification channels: ntfy, Telegram, and email (SMTP)
- Baseline learning mode to suppress alerts during initial deployment
- JSON output format (`--json`) for machine-readable reports
- Severity classification and filtering (`--min-severity`)
- Man page (`man log-whisperer`)

### Changed
- Environment variable prefix renamed from `LOGWHISPER_` to `LOGWHISPERER_`

## [0.1.0] - 2026-02-09

### Added
- Initial release
- Multi-source log reading: Docker, Compose, systemd journal, plain files
- Pattern normalization (IPs, UUIDs, timestamps, paths, numbers)
- Pattern clustering and new-pattern detection
- JSON-lines database with file-level locking
- CI pipeline with Python 3.9-3.13 matrix
