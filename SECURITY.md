# Security

This is a static site with no backend, accounts, cookies or user data.

- Pages ship a strict Content-Security-Policy: scripts and styles only from this
  site, no inline scripts, no third-party requests.
- CI pins every GitHub Action to a commit SHA, installs only from lockfiles, and
  deploys only after build, tests, lint, accessibility and page checks pass.
- Dependabot keeps actions and dependencies current.

To report a problem, open a private security advisory on this repository
(Security tab → Report a vulnerability). Please don't file public issues for
security reports.
