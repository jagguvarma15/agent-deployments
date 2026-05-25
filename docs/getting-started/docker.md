# Docker

> Container runtime. `agent-scaffold` and most recipes assume you can run `docker run` against a working daemon for Redis, Postgres, Kafka, and so on.

**Signup**: not required.

## Install

### macOS

Either:

```bash
brew install --cask docker            # Docker Desktop (most common)
# or:
brew install colima docker            # Colima — lighter, no Desktop UI
colima start                          # one-time
```

Colima is the recommended option if you're avoiding Docker Desktop licensing.

### Linux

The official convenience script handles Debian / Ubuntu / Fedora / RHEL:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"        # then log out + back in
```

Full per-distro instructions: https://docs.docker.com/engine/install/

### Windows

Install **Docker Desktop** with the WSL2 backend:

1. Install WSL2 (`wsl --install` from an admin PowerShell)
2. Install Docker Desktop from https://docker.com/products/docker-desktop
3. In Settings → Resources → WSL Integration, enable your distro

## Verify

```bash
docker info                            # → shows Server info section
docker run --rm hello-world            # → "Hello from Docker!"
```

`docker info` exiting 0 with a `Server:` section is the canonical "daemon is up" check that `agent-scaffold doctor` uses.

## Wire into your project

Recipes that need local services bundle a `docker-compose.yml`. Bring everything up with:

```bash
docker compose up -d
docker compose ps                      # confirm services healthy
docker compose logs -f redis           # tail one service
docker compose down                    # stop + remove
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot connect to the Docker daemon` | Daemon not running | Start Docker Desktop or `colima start` |
| `permission denied while trying to connect` (Linux) | User not in the `docker` group | `sudo usermod -aG docker "$USER"`; log out + back in |
| `port is already allocated` | Another container or process owns the port | `docker ps`; `lsof -i :6379`; stop the offender |
| `no space left on device` | Image / volume buildup | `docker system prune -af --volumes` (destructive) |
| Apple Silicon: `image not available for arm64` | Image was published only for `amd64` | `docker run --platform linux/amd64 ...` (slow via emulation) |

## See also

- [`docs/reference/`](../reference/) — Dockerfile and docker-compose templates
- Upstream install docs: https://docs.docker.com/engine/install/
