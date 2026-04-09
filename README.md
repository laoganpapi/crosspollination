# Crosspollination

An MCP server that connects Claude to **multiple Google Drive accounts** simultaneously. Access files from your personal and work Drives in a single session without switching accounts.

## Features

- **Multi-account support** — Connect unlimited Google Drive accounts (personal, work, school, etc.)
- **Encrypted credential storage** — All OAuth tokens are encrypted at rest with AES-256-GCM
- **Cross-account search** — Search for files across all connected accounts at once
- **Google Workspace support** — Read Google Docs (as text), Sheets (as CSV), Slides, and regular files
- **Account labeling** — Label each account ("personal", "work") so results are always clear

## Setup

### 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project (or use an existing one)
3. Enable the **Google Drive API** and **Google OAuth2 API**
4. Create an **OAuth 2.0 Client ID** (type: Desktop App)
5. Note the **Client ID** and **Client Secret**

### 2. Generate an Encryption Key

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### 3. Install & Build

```bash
npm install
npm run build
```

### 4. Configure Claude

Add to your Claude MCP settings (`~/.claude/claude_mcp_config.json` or equivalent):

```json
{
  "mcpServers": {
    "crosspollination": {
      "command": "node",
      "args": ["dist/index.js"],
      "cwd": "/absolute/path/to/crosspollination",
      "env": {
        "GOOGLE_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "your-client-secret",
        "ENCRYPTION_KEY": "your-64-char-hex-key"
      }
    }
  }
}
```

## Usage

Once configured, Claude has access to these tools:

### Account Management

| Tool | Description |
|------|-------------|
| `add_account` | Connect a new Google Drive account with a label |
| `list_accounts` | Show all connected accounts |
| `remove_account` | Disconnect an account |

### File Operations

| Tool | Description |
|------|-------------|
| `search_drive` | Search files in specific or all accounts |
| `cross_account_search` | Unified search across every connected account |
| `list_drive_files` | Browse files/folders in an account |
| `read_drive_file` | Read file contents (Docs, Sheets, text files) |
| `get_file_info` | Get file metadata (size, type, link) |

### Example Conversations

**Connect accounts:**
> "Connect my personal Gmail Drive as 'personal'"
> "Now add my work account as 'work'"

**Search across accounts:**
> "Find the Q4 budget spreadsheet — I'm not sure if it's in my personal or work Drive"

**Read files:**
> "Read the meeting notes from my work Drive"

## Security

- OAuth tokens are encrypted with AES-256-GCM before being written to disk
- The credential store (`~/.crosspollination/accounts.enc.json`) is created with `600` permissions (owner-only read/write)
- The encryption key never touches disk — it's passed via environment variable
- OAuth flow uses CSRF protection via state parameter
- Drive access is **read-only** — this server cannot modify or delete your files

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | OAuth2 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth2 client secret |
| `ENCRYPTION_KEY` | Yes | 64-char hex string for AES-256-GCM encryption |
| `OAUTH_CALLBACK_PORT` | No | Port for OAuth callback server (default: 3847) |
| `CROSSPOLLINATION_DATA_DIR` | No | Custom directory for credential storage (default: `~/.crosspollination`) |
