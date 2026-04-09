import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  getAllAccounts,
  removeAccount,
  getAccount,
  validateEncryptionKey,
} from "./auth/store.js";
import { authenticateAccount, revokeToken } from "./auth/oauth.js";
import {
  listFiles,
  searchFiles,
  readFile,
  getFileMetadata,
} from "./drive/client.js";
import { sanitizeErrorMessage } from "./sanitize.js";

// ─── Startup validation ────────────────────────────────────────────────────

function validateEnvironment(): void {
  validateEncryptionKey();

  if (!process.env.GOOGLE_CLIENT_ID || !process.env.GOOGLE_CLIENT_SECRET) {
    throw new Error(
      "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set. " +
        "Create OAuth credentials at https://console.cloud.google.com/apis/credentials",
    );
  }
}

// ─── Server ─────────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "crosspollination",
  version: "1.0.0",
});

// ─── Account Management Tools ───────────────────────────────────────────────

server.tool(
  "add_account",
  "Connect a new Google Drive account. Opens a browser for OAuth login. " +
    "Use a label like 'personal' or 'work' to identify the account. " +
    "Labels must be 1-64 characters: letters, numbers, spaces, hyphens, underscores, periods.",
  {
    label: z
      .string()
      .min(1)
      .max(64)
      .describe(
        "A friendly label for this account, e.g. 'personal' or 'work'",
      ),
  },
  async ({ label }) => {
    try {
      const account = await authenticateAccount(label);
      return {
        content: [
          {
            type: "text" as const,
            text: `Successfully connected account "${account.label}" (${account.email}). Account ID: ${account.id}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to connect account: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "list_accounts",
  "List all connected Google Drive accounts with their labels, emails, and IDs.",
  {},
  async () => {
    try {
      const accounts = await getAllAccounts();
      if (accounts.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: 'No accounts connected yet. Use "add_account" to link a Google Drive.',
            },
          ],
        };
      }

      const lines = accounts.map(
        (a) =>
          `- ${a.label} | ${a.email} | ID: ${a.id} | added: ${a.addedAt}`,
      );
      return {
        content: [
          {
            type: "text" as const,
            text: `Connected accounts (${accounts.length}):\n${lines.join("\n")}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to list accounts: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "remove_account",
  "Disconnect a Google Drive account. Revokes the OAuth token with Google and deletes local credentials.",
  { account_id: z.string().describe("The account ID to remove") },
  async ({ account_id }) => {
    try {
      const account = await getAccount(account_id);
      if (!account) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No account found with ID: ${account_id}`,
            },
          ],
          isError: true,
        };
      }

      // Revoke the token with Google before deleting locally
      await revokeToken(account.tokens);
      await removeAccount(account_id);

      return {
        content: [
          {
            type: "text" as const,
            text: `Removed account "${account.label}" (${account.email}). OAuth token has been revoked.`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to remove account: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ─── File Operation Tools ───────────────────────────────────────────────────

server.tool(
  "search_drive",
  "Search for files across all connected Google Drive accounts, or limit to specific ones. " +
    "Results are grouped by account. If any account fails (e.g. expired token), you'll be told which ones.",
  {
    query: z
      .string()
      .min(1)
      .describe("Search query — searches file names and content"),
    account_ids: z
      .array(z.string())
      .optional()
      .describe(
        "Optional: limit search to specific account IDs. Omit to search all accounts.",
      ),
  },
  async ({ query, account_ids }) => {
    try {
      const { results, errors } = await searchFiles(query, account_ids);

      const parts: string[] = [];

      if (results.every((r) => r.files.length === 0) && errors.length === 0) {
        parts.push(
          `No files found matching "${query}" in any connected account.`,
        );
      } else {
        const sections = results.map((r) => {
          if (r.files.length === 0)
            return `[${r.accountLabel}]: No results`;
          const fileLines = r.files.map(
            (f) =>
              `  - ${f.name} (${f.mimeType}) | ID: ${f.id}${f.modifiedTime ? ` | modified: ${f.modifiedTime}` : ""}`,
          );
          return `[${r.accountLabel}] (${r.files.length} results):\n${fileLines.join("\n")}`;
        });
        parts.push(
          `Search results for "${query}":\n\n${sections.join("\n\n")}`,
        );
      }

      if (errors.length > 0) {
        const errorLines = errors.map(
          (e) => `  - ${e.accountLabel}: ${e.error}`,
        );
        parts.push(
          `\nFailed to search ${errors.length} account(s):\n${errorLines.join("\n")}`,
        );
      }

      return {
        content: [{ type: "text" as const, text: parts.join("\n") }],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Search failed: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "list_drive_files",
  "List files in a Google Drive account, optionally within a specific folder.",
  {
    account_id: z.string().describe("The account ID to list files from"),
    folder_id: z
      .string()
      .optional()
      .describe("Optional folder ID to list contents of"),
    page_size: z
      .number()
      .int()
      .min(1)
      .max(100)
      .optional()
      .describe("Number of files to return (1-100, default 20)"),
    page_token: z
      .string()
      .optional()
      .describe("Pagination token from a previous response"),
  },
  async ({ account_id, folder_id, page_size, page_token }) => {
    try {
      const result = await listFiles(
        account_id,
        folder_id,
        page_size,
        page_token,
      );
      const account = await getAccount(account_id);

      if (result.files.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No files found in ${account?.label || account_id}.`,
            },
          ],
        };
      }

      const fileLines = result.files.map(
        (f) =>
          `- ${f.name} (${f.mimeType}) | ID: ${f.id}${f.modifiedTime ? ` | modified: ${f.modifiedTime}` : ""}`,
      );

      let text = `Files in ${account?.label || account_id} (${result.files.length}):\n${fileLines.join("\n")}`;
      if (result.nextPageToken) {
        text += `\n\n[More files available — use page_token: "${result.nextPageToken}"]`;
      }

      return { content: [{ type: "text" as const, text }] };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to list files: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "read_drive_file",
  "Read the content of a file from Google Drive. Works with Google Docs, Sheets (exported as CSV), " +
    "and regular text files. Large files are truncated or return a link instead.",
  {
    account_id: z.string().describe("The account ID that owns the file"),
    file_id: z.string().describe("The file ID to read"),
  },
  async ({ account_id, file_id }) => {
    try {
      const result = await readFile(account_id, file_id);
      return {
        content: [
          {
            type: "text" as const,
            text: `${result.name} (${result.mimeType}):\n\n${result.content}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to read file: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "get_file_info",
  "Get metadata about a specific file (name, type, size, last modified, link).",
  {
    account_id: z.string().describe("The account ID that owns the file"),
    file_id: z.string().describe("The file ID to get info for"),
  },
  async ({ account_id, file_id }) => {
    try {
      const file = await getFileMetadata(account_id, file_id);
      const lines = [
        `Name: ${file.name}`,
        `Type: ${file.mimeType}`,
        `Account: ${file.account}`,
        file.size
          ? `Size: ${(parseInt(file.size) / 1024).toFixed(1)} KB`
          : null,
        file.modifiedTime ? `Modified: ${file.modifiedTime}` : null,
        file.webViewLink ? `Link: ${file.webViewLink}` : null,
      ].filter(Boolean);

      return { content: [{ type: "text" as const, text: lines.join("\n") }] };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to get file info: ${sanitizeErrorMessage(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ─── Start Server ───────────────────────────────────────────────────────────

async function main() {
  validateEnvironment();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Crosspollination MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err instanceof Error ? err.message : err);
  process.exit(1);
});
