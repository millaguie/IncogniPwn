# IncogniPwn

**Privacy-preserving, self-hosted HIBP Pwned Passwords k-anonymity API.**

Check if a password has been compromised in a data breach — without ever leaking any information to third parties.

---

## Why?

When you use the [Have I Been Pwned API](https://haveibeenpwned.com/API/v3#PwnedPasswords), you send the first 5 characters of your password's SHA-1 hash to an external service. While the k-anonymity model is clever, it still reveals:

- **What prefix you're querying** — and when, and how often
- **Usage patterns** — which passwords are being checked in your organization
- **Timing information** — that can correlate with user activity

For organizations handling sensitive authentication (password managers, SSO providers, internal security tools), this is a privacy risk. **IncogniPwn** runs entirely inside your infrastructure. No data leaves your network. No API keys. No tracking.

> **Threat model note:** IncogniPwn eliminates the query-side privacy risk (what you search, when, and how often). However, an attacker with access to your infrastructure will discover that you possess the full HIBP password hash corpus. This is a trade-off: you gain query privacy at the cost of storing ~80GB of breach data locally. Assess whether this is acceptable for your threat model.
>
> **Logging warning:** Application logs may record the hash prefixes being queried, effectively leaking internally the same information you are trying to protect from HIBP. In production, consider disabling debug logging, sending logs to a restricted-access destination, or configuring log aggregation with appropriate access controls.

## What it does

IncogniPwn provides a fully compatible implementation of the HIBP Pwned Passwords `/range/{prefix}` endpoint. It uses the official [PwnedPasswordsDownloader](https://github.com/HaveIBeenPwned/PwnedPasswordsDownloader) to download the full password hash corpus and keep it updated automatically.

Drop-in replacement for `https://api.pwnedpasswords.com/range/` — works with any tool that expects the HIBP API format (Ory Kratos, Passbolt, custom password validators, browser extensions, etc.).

## Features

- **HIBP-compatible API** — `GET /range/{prefix}` returns hash suffixes with prevalence counts
- **Add-Padding support** — pads responses to 800-1000 entries, matching HIBP privacy behavior
- **Automatic updates** — CronJob downloads new data weekly via the official downloader
- **Atomic updates** — downloader validates file count before swapping, never serves partial data
- **Kubernetes-ready** — Helm chart with HPA, PDB, Ingress, ServiceMonitor
- **Local development** — docker-compose for testing without a cluster
- **Zero dependencies** — no database, reads files directly (O(1) lookup by filename)

## Quick Start

### Docker Compose (local)

```bash
# First run: download the full corpus (~80GB)
docker compose run --rm downloader

# Then start the API
docker compose up api

# Test it
curl http://localhost:8000/range/21BD1
```

### Kubernetes (Helm)

Pre-built images are available at `ghcr.io/millaguie/incognipwn-api` and `ghcr.io/millaguie/incognipwn-downloader`.

```bash
# Install with production values (images are pulled from GHCR by default)
helm install incognipwn ./chart/incognipwn \
  -n incognipwn --create-namespace \
  -f ./chart/incognipwn/values/prod.yaml

# Or override with your own registry
helm install incognipwn ./chart/incognipwn \
  -n incognipwn --create-namespace \
  -f ./chart/incognipwn/values/prod.yaml \
  --set api.image.repository=your-registry/incognipwn-api \
  --set downloader.image.repository=your-registry/incognipwn-downloader

# Test
curl http://incognipwn.example.com/range/21BD1
```

## API Reference

### `GET /range/{prefix}`

Returns all SHA-1 hash suffixes matching the 5-character hex prefix, with their prevalence counts.

**Parameters:**
- `prefix` — 5 hexadecimal characters (case-insensitive)

**Headers:**
| Header | Value | Description |
|---|---|---|
| `Add-Padding` | `true` | Pads response to 800-1000 entries with random fake suffixes (count=0) |

**Example:**
```
$ curl http://localhost:8000/range/21BD1

0018A45C4D1DEF81644B54AB7F969B88D65:1
00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2
011053FD0102E94D6AE2F8B83D76FAF94F6:1
...
```

### `GET /health`

Returns `{"status": "ok"}`. Always returns 200.

### `GET /ready`

Returns `{"status": "ready"}` if hash data is available, 503 otherwise.

## Architecture

```
                    ┌───────────────┐
                    │   Ingress     │
                    │(nginx/traefik)│
                    └──────┬────────┘
                           │
                    ┌──────▼──────┐
                    │   Service   │
                    │ ClusterIP   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐┌─────▼────┐┌──────▼───┐
        │  API Pod  ││ API Pod  ││ API Pod  │
        │ (FastAPI) ││(FastAPI) ││(FastAPI) │
        └─────┬─────┘└─────┬────┘└──────┬───┘
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │    PVC       │
                    │ ReadWriteMany│
                    │  ~80GB       │
                    │ /data/hashes │
                    └──────▲───────┘
                           │
                    ┌──────┴──────┐
                    │  CronJob    │
                    │ (Downloader)│
                    │  weekly     │
                    └─────────────┘
```

**How it works:**

1. The downloader fetches all ~1M hash range files (one per 5-char prefix, `00000.txt` through `FFFFF.txt`) from HIBP
2. Files are stored on a shared PVC (~80GB)
3. The API serves each file directly — O(1) lookup, no database needed
4. A CronJob re-runs the downloader weekly to pick up new breach data
5. Updates are atomic: download to temp dir, validate file count, then rsync into place

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data/hashes` | Path to hash files directory |
| `HASH_OUTPUT_DIR` | `/data/hashes` | Final hash output path (downloader) |
| `HASH_TEMP_DIR` | `/data/hashes-new` | Temp download path (downloader) |
| `PARALLELISM` | `64` | Parallel download threads (downloader) |
| `OVERWRITE` | `true` | Overwrite existing files (downloader) |

### Helm Values

See [`chart/incognipwn/values.yaml`](chart/incognipwn/values.yaml) for the full reference. Key values:

```yaml
api:
  replicas: 3
  ingress:
    host: incognipwn.example.com
  hpa:
    maxReplicas: 10

downloader:
  schedule: "0 3 * * 0"   # Weekly, Sunday 3AM

storage:
  size: 25Gi
  storageClassName: nfs    # Must be ReadWriteMany
```

### Makefile Targets

```
make dev              # Run full local environment
make dev-api          # Run API only (data must exist)
make dev-download     # Run downloader only
make test             # Run tests
make build            # Build Docker images
make chart-install    # Install Helm chart
make chart-install-prod  # Install with prod values
```

## Contributing

Contributions are welcome. To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Ensure linting passes (`make lint`)
6. Open a Pull Request

### Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx pytest
PYTHONPATH=api pytest tests/ -v
```

### Project structure

```
api/                  # FastAPI application
  app/
    routes/range.py   # /range, /health, /ready endpoints
    services/         # Hash lookup + padding logic
downloader/           # .NET downloader + atomic update script
chart/incognipwn/     # Helm chart
  templates/          # K8s manifests
  values/             # dev.yaml, prod.yaml overlays
tests/                # Pytest test suite
```

## Vibecoded

This project was **vibecoded** — the codebase was generated through an interactive AI-assisted session. The entire architecture, implementation, Helm chart, test suite, and documentation were produced collaboratively with **GLM-5.1** as co-author.

### Original Prompt

> I want to run a service on a Kubernetes cluster that is similar to the Have I Been Pwned API, specifically the `/range` endpoint. The service should receive a partial SHA-1 hash prefix (first 5 characters) and return all matching hash suffixes with their occurrence counts — exactly like the HIBP Pwned Passwords k-anonymity API (`GET /range/{prefix}`).
>
> Additionally, the service must use the [PwnedPasswordsDownloader](https://github.com/HaveIBeenPwned/PwnedPasswordsDownloader) tool to download and keep the password hash database updated.

### Design Rationale

| Decision | Choice | Why |
|---|---|---|
| Language | Python (FastAPI) | Ergonomic async, broad ecosystem, easy to containerize |
| Storage | Individual files (~1M, one per prefix) | O(1) lookup by filename, no database dependency, ~80GB total |
| Hash format | SHA-1 only | Matches HIBP; NTLM not needed |
| Updates | Weekly CronJob | HIBP updates quarterly; weekly catches changes promptly |
| Deployment | Helm + docker-compose | K8s for production, compose for local dev |

### Existing Alternatives

No existing project provides a well-maintained, Kubernetes-ready, HIBP `/range/{prefix}`-compatible API:

- **radekg/hibp** (Go, PostgreSQL) — requires 613M+ rows, no K8s
- **felix-engelmann/haveibeenpwned-api** (Python/Flask) — abandoned, flat file + binary search
- **oschonrock/hibp** (C++) — active, but NOT `/range/` compatible
- **easybill/easypwned** (Rust) — active, bloom filter, NOT `/range/` compatible

## License

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.

The password hash data is sourced from [Have I Been Pwned](https://haveibeenpwned.com/Passwords) by Troy Hunt, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
