# Obsidian Local REST API Cheat Sheet

## Installation

1. Obsidian > Settings > Community Plugins > Browse
2. Search "Local REST API" by coddingtonbear
3. Install, then Enable
4. An API key is auto-generated (SHA-256 of 128 random bytes). Find it in the plugin's settings panel.

## Core API

### Server

| Protocol | URL | Default |
|---|---|---|
| HTTPS | `https://127.0.0.1:27124` | Enabled |
| HTTP | `http://127.0.0.1:27123` | Disabled |

The HTTPS server uses a self-signed certificate (2048-bit RSA, 365-day validity). Download it from `GET /cert.pem` to trust it locally, or disable TLS verification in your client.

### Authentication

Every request (except `GET /`, `GET /cert.pem`, `GET /openapi.yaml`) requires:

```
Authorization: Bearer <your-api-key>
```

The header name is configurable in settings but defaults to `Authorization`.

### Content Types

| Content-Type | Use |
|---|---|
| `text/markdown` | Plain markdown body |
| `application/json` | JSON payloads |
| `application/vnd.olrapi.note+json` | Structured note with frontmatter metadata |
| `*/*` | Binary files (images, PDFs) |

For responses, set `Accept: application/vnd.olrapi.note+json` to get metadata alongside content.

### Vault File Endpoints

All paths are relative to vault root. The `*` is the file path (e.g., `/vault/folder/note.md`).

| Method | Path | What it does |
|---|---|---|
| `GET` | `/vault/{path}` | Read file content, or list directory contents |
| `PUT` | `/vault/{path}` | Create or overwrite file |
| `POST` | `/vault/{path}` | Append content to existing file |
| `PATCH` | `/vault/{path}` | Insert/replace content at a heading, block ref, or frontmatter key |
| `DELETE` | `/vault/{path}` | Delete file |

### Active File Endpoints

Same verbs as vault, but operates on whichever file is currently open in the Obsidian editor.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/active/` | Read currently open file |
| `PUT` | `/active/` | Replace active file content |
| `POST` | `/active/` | Append to active file |
| `PATCH` | `/active/` | Patch active file at heading/block |
| `DELETE` | `/active/` | Delete the active file |

### Periodic Notes

Works with daily, weekly, monthly, quarterly, yearly notes. Requires the Periodic Notes or Daily Notes plugin.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/periodic/daily/` | Get today's daily note (creates if absent) |
| `GET` | `/periodic/daily/{year}/{month}/{day}/` | Get a specific day's note |
| `PUT` | `/periodic/daily/` | Replace today's note |
| `POST` | `/periodic/daily/` | Append to today's note |
| `PATCH` | `/periodic/daily/` | Patch today's note |
| `DELETE` | `/periodic/daily/` | Delete today's note |

Replace `daily` with `weekly`, `monthly`, `quarterly`, or `yearly`.

### Commands

| Method | Path | What it does |
|---|---|---|
| `GET` | `/commands/` | List all commands (returns `[{id, name}]`) |
| `POST` | `/commands/{commandId}/` | Execute a command by ID |

### Search

| Method | Path | Content-Type | What it does |
|---|---|---|---|
| `POST` | `/search/simple/` | `text/plain` | Full-text search with context |
| `POST` | `/search/` | `application/vnd.olrapi.dataview-dql+txt` | Dataview DQL query |
| `POST` | `/search/` | `application/vnd.olrapi.jsonlogic+json` | JSON Logic query |

### Misc

| Method | Path | What it does |
|---|---|---|
| `POST` | `/open/{path}` | Open a file in the Obsidian UI |
| `GET` | `/` | API status (no auth required) |
| `GET` | `/cert.pem` | Download the self-signed cert (no auth required) |

## Usage Patterns

### 1. Create a new note

```bash
curl -X PUT "https://127.0.0.1:27124/vault/Projects/my-note.md" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: text/markdown" \
  -d "# My Note\n\nContent here." \
  --insecure
```

### 2. Append to today's daily note

```bash
curl -X POST "https://127.0.0.1:27124/periodic/daily/" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: text/markdown" \
  -d "\n## Evening\nWrapped up the watchdog integration." \
  --insecure
```

### 3. Read a note as structured JSON (with frontmatter)

```bash
curl "https://127.0.0.1:27124/vault/Projects/my-note.md" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/vnd.olrapi.note+json" \
  --insecure
```

### 4. Patch content under a specific heading

```bash
curl -X PATCH "https://127.0.0.1:27124/vault/Projects/my-note.md" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"heading": "Status", "content": "In progress"}' \
  --insecure
```

### 5. Python requests example

```python
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://127.0.0.1:27124"
HEADERS = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "text/markdown",
}

# Create a note
requests.put(
    f"{BASE}/vault/Inbox/from-script.md",
    headers=HEADERS,
    data="# Auto-generated\n\nCreated by script.",
    verify=False,
)

# List vault root
resp = requests.get(f"{BASE}/vault/", headers=HEADERS, verify=False)
print(resp.json())
```

## Common Pitfalls

- **Self-signed cert.** Every HTTP client will reject the cert by default. Either download `/cert.pem` and trust it, or use `verify=False` / `--insecure`. Don't forget this or every request fails silently.
- **Trailing slashes matter.** `/vault/folder` and `/vault/folder/` can behave differently. Directory listings need the trailing slash.
- **HTTP is disabled by default.** If you don't want to deal with certs during local dev, enable the HTTP server (port 27123) in plugin settings. Not recommended for anything exposed beyond localhost.
- **PATCH requires structure.** You can't just send raw text to PATCH. You need to specify which heading, block reference, or frontmatter field to target.
- **Obsidian must be running.** The API is served by the Obsidian app process. No Obsidian, no API.
- **Rate limits aren't documented.** The plugin doesn't enforce rate limits, but hammering it with rapid requests while Obsidian is syncing can cause conflicts.

## Sources

- [GitHub](https://github.com/coddingtonbear/obsidian-local-rest-api)
- [Interactive API Docs (Swagger)](https://coddingtonbear.github.io/obsidian-local-rest-api/)
- [DeepWiki Reference](https://deepwiki.com/coddingtonbear/obsidian-local-rest-api)
