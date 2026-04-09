import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  getAllAccounts,
  removeAccount,
  getAccount,
} from "./auth/store.js";
import { authenticateAccount } from "./auth/oauth.js";
import {
  listFiles,
  searchFiles,
  readFile,
  getFileMetadata,
} from "./drive/client.js";

const server = new McpServer({
  name: "crosspollination",
  version: "1.0.0",
});

// ─── Account Management Tools ───────────────────────────────────────────────

server.tool(
  "add_account",
  "Connect a new Google Drive account. Opens a browser for OAuth login. " +
    "Use a label like 'personal' or 'work' to identify the account.",
  { label: z.string().describe("A friendly label for this account, e.g. 'personal' or 'work'") },
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
            text: `Failed to connect account: ${err instanceof Error ? err.message : String(err)}`,
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
    const accounts = await getAllAccounts();
    if (accounts.length === 0) {
      return {
        content: [
          {
            type: "text" as const,
            text: 'No accounts connected yet. Use the "add_account" tool to connect a Google Drive account.',
          },
        ],
      };
    }

    const lines = accounts.map(
      (a) => `• ${a.label} — ${a.email} (ID: ${a.id}, added: ${a.addedAt})`,
    );
    return {
      content: [
        {
          type: "text" as const,
          text: `Connected accounts (${accounts.length}):\n${lines.join("\n")}`,
        },
      ],
    };
  },
);

server.tool(
  "remove_account",
  "Disconnect a Google Drive account by its ID.",
  { account_id: z.string().describe("The account ID to remove") },
  async ({ account_id }) => {
    const account = await getAccount(account_id);
    const removed = await removeAccount(account_id);
    if (!removed) {
      return {
        content: [
          { type: "text" as const, text: `No account found with ID: ${account_id}` },
        ],
        isError: true,
      };
    }
    return {
      content: [
        {
          type: "text" as const,
          text: `Removed account "${account?.label}" (${account?.email}).`,
        },
      ],
    };
  },
);

// ─── File Operation Tools ───────────────────────────────────────────────────

server.tool(
  "search_drive",
  "Search for files across all connected Google Drive accounts (or specific ones). " +
    "Returns results grouped by account so you can see which Drive each file belongs to.",
  {
    query: z.string().describe("Search query — searches file names and content"),
    account_ids: z
      .array(z.string())
      .optional()
      .describe("Optional: limit search to specific account IDs. Omit to search all accounts."),
  },
  async ({ query, account_ids }) => {
    try {
      const results = await searchFiles(query, account_ids);
      if (results.every((r) => r.files.length === 0)) {
        return {
          content: [
            { type: "text" as const, text: `No files found matching "${query}" in any connected account.` },
          ],
        };
      }

      const sections = results.map((r) => {
        if (r.files.length === 0) return `📁 ${r.accountLabel}: No results`;
        const fileLines = r.files.map(
          (f) =>
            `  • ${f.name} (${f.mimeType}) — ID: ${f.id}${f.modifiedTime ? `, modified: ${f.modifiedTime}` : ""}`,
        );
        return `📁 ${r.accountLabel} (${r.files.length} results):\n${fileLines.join("\n")}`;
      });

      return {
        content: [
          {
            type: "text" as const,
            text: `Search results for "${query}":\n\n${sections.join("\n\n")}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Search failed: ${err instanceof Error ? err.message : String(err)}`,
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
    folder_id: z.string().optional().describe("Optional folder ID to list contents of"),
    page_size: z.number().min(1).max(100).optional().describe("Number of files to return (1-100, default 20)"),
    page_token: z.string().optional().describe("Pagination token from a previous response"),
  },
  async ({ account_id, folder_id, page_size, page_token }) => {
    try {
      const result = await listFiles(account_id, folder_id, page_size, page_token);
      const account = await getAccount(account_id);

      if (result.files.length === 0) {
        return {
          content: [
            { type: "text" as const, text: `No files found in ${account?.label || account_id}.` },
          ],
        };
      }

      const fileLines = result.files.map(
        (f) =>
          `• ${f.name} (${f.mimeType}) — ID: ${f.id}${f.modifiedTime ? `, modified: ${f.modifiedTime}` : ""}`,
      );

      let text = `Files in ${account?.label || account_id} (${result.files.length}):\n${fileLines.join("\n")}`;
      if (result.nextPageToken) {
        text += `\n\n[More files available — use page_token: "${result.nextPageToken}" to continue]`;
      }

      return { content: [{ type: "text" as const, text }] };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to list files: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

server.tool(
  "read_drive_file",
  "Read the content of a file from Google Drive. Works with Google Docs, Sheets (as CSV), " +
    "and regular text files. Large binary files will return a link instead.",
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
            text: `📄 ${result.name} (${result.mimeType}):\n\n${result.content}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to read file: ${err instanceof Error ? err.message : String(err)}`,
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
        file.size ? `Size: ${(parseInt(file.size) / 1024).toFixed(1)} KB` : null,
        file.modifiedTime ? `Modified: ${file.modifiedTime}` : null,
        file.webViewLink ? `Link: ${file.webViewLink}` : null,
      ].filter(Boolean);

      return { content: [{ type: "text" as const, text: lines.join("\n") }] };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to get file info: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ─── Cross-Account Tools ────────────────────────────────────────────────────

server.tool(
  "cross_account_search",
  "Search across ALL connected accounts simultaneously and return a unified view. " +
    "Great for finding a file when you don't remember which Drive it's in.",
  {
    query: z.string().describe("Search query"),
  },
  async ({ query }) => {
    try {
      const accounts = await getAllAccounts();
      if (accounts.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: "No accounts connected. Use add_account to connect Google Drive accounts first.",
            },
          ],
        };
      }

      const results = await searchFiles(query);
      const allFiles = results.flatMap((r) =>
        r.files.map((f) => ({ ...f, accountId: r.account, accountLabel: r.accountLabel })),
      );

      if (allFiles.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No files found matching "${query}" across ${accounts.length} account(s).`,
            },
          ],
        };
      }

      // Sort by modified time across all accounts
      allFiles.sort((a, b) => {
        const ta = a.modifiedTime ? new Date(a.modifiedTime).getTime() : 0;
        const tb = b.modifiedTime ? new Date(b.modifiedTime).getTime() : 0;
        return tb - ta;
      });

      const lines = allFiles.map(
        (f) =>
          `• [${f.accountLabel}] ${f.name} (${f.mimeType}) — account: ${f.accountId}, file: ${f.id}${f.modifiedTime ? `, modified: ${f.modifiedTime}` : ""}`,
      );

      return {
        content: [
          {
            type: "text" as const,
            text: `Found ${allFiles.length} file(s) across ${results.length} account(s) for "${query}":\n\n${lines.join("\n")}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Cross-account search failed: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ─── Start Server ───────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Crosspollination MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
