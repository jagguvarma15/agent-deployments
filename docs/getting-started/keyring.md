# Keyring

> OS-backed secret storage. `agent-scaffold auth login` uses `python-keyring` to put your Anthropic key in macOS Keychain / Windows Credential Manager / Linux Secret Service instead of your shell history.

**Signup**: not required.

## How it works per OS

| OS | Backend | Setup needed |
|----|---------|--------------|
| macOS | Keychain (via Security framework) | none — works as soon as you're logged in |
| Windows | Credential Manager | none |
| Linux desktop (GNOME) | GNOME Keyring (Secret Service) | `gnome-keyring-daemon` running; usually auto-started by the session |
| Linux desktop (KDE) | KWallet (Secret Service) | `kwalletd` running |
| Linux headless / WSL / Docker | no native backend | `agent-scaffold` refuses plaintext and falls back to a mode-0600 file |

## Verify

```bash
agent-scaffold auth status
```

A healthy native backend prints e.g. `Backend: macOS Keychain good`.

To test the underlying library directly:

```bash
uv run python -c "import keyring; print(keyring.get_keyring())"
```

You want one of: `keyring.backends.macOS.Keyring`, `keyring.backends.Windows.WinVaultKeyring`, `keyring.backends.SecretService.Keyring`, `keyrings.kwallet.KWallet5`.

## Wire into your project

You don't — `agent-scaffold` does it for you:

```bash
agent-scaffold auth login                  # native flow
agent-scaffold auth setup-token ci-prod    # file backend (for CI / headless)
```

The plaintext fallback (`keyrings.alt`) is **refused on purpose** — silently writing secrets to a world-readable file would defeat the entire keyring story. If no native backend is available, use the mode-0600 credentials file instead.

## Linux desktop: get the daemon running

If `agent-scaffold auth status` reports `Refusing keyring backend: ...`:

```bash
# GNOME
systemctl --user status gnome-keyring-daemon
systemctl --user enable --now gnome-keyring-daemon

# KDE
systemctl --user status kwalletd5
systemctl --user enable --now kwalletd5
```

You may also need to unlock the keyring on first use — a GUI prompt appears asking for your login password.

## WSL specifically

DBus inside WSL is fiddly and the Secret Service rarely Just Works. Recommended:

```bash
agent-scaffold auth setup-token wsl --stdin <<< "$ANTHROPIC_API_KEY"
```

This writes `$XDG_CONFIG_HOME/agent-scaffold/credentials` at mode 0600 — secure-enough for a single-user WSL distro.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `keyring.errors.NoKeyringError` | No usable backend on this system | Use `--use-file` or `agent-scaffold auth setup-token ... --stdin` |
| `Refusing keyring backend: PlaintextKeyring` | `keyrings.alt` is installed | Don't install `keyrings.alt`; use the file backend instead |
| `org.freedesktop.DBus.Error.NoReply` (Linux) | DBus session bus not exported | Run inside a proper user session (not `sudo`/cron); `dbus-launch` in headless setups |
| Keychain prompts every run (macOS) | "Always Allow" not granted | First prompt: click **Always Allow** for `agent-scaffold` to remember the grant |

## See also

- `python-keyring` upstream: https://github.com/jaraco/keyring (see the Linux section for backend-specific gotchas)
- Secret Service spec: https://specifications.freedesktop.org/secret-service/latest/
- [`docs/cross-cutting/security-hardening.md`](../cross-cutting/security-hardening.md) — broader secret-handling guidance
