import { google, type drive_v3 } from "googleapis";
import { createAuthenticatedClient } from "../auth/oauth.js";
import { getAllAccounts, getAccount, saveAccount } from "../auth/store.js";
import { sanitizeErrorMessage } from "../sanitize.js";
import type { AccountInfo, DriveFile, SearchResult } from "../types.js";

// ─── Rate limiting ──────────────────────────────────────────────────────────

// Google Drive API default quota: 12,000 requests per minute per project.
// We enforce a per-account limit to stay safely below that.
const RATE_WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 30; // per account

const requestLog = new Map<string, number[]>();

function checkRateLimit(accountId: string): void {
  const now = Date.now();
  let timestamps = requestLog.get(accountId) || [];
  timestamps = timestamps.filter((t) => now - t < RATE_WINDOW_MS);

  if (timestamps.length >= MAX_REQUESTS_PER_WINDOW) {
    throw new Error(
      `Rate limit reached for account ${accountId}. ` +
        `Max ${MAX_REQUESTS_PER_WINDOW} requests per minute. Try again shortly.`,
    );
  }

  timestamps.push(now);
  requestLog.set(accountId, timestamps);
}

// ─── Query sanitization ────────────────────────────────────────────────────

// Google Drive query language uses single-quoted strings.
// Escape backslashes first, then single quotes.
function sanitizeQueryValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// Google Drive file IDs are alphanumeric with hyphens and underscores.
const FILE_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

function validateFileId(fileId: string): void {
  if (!fileId || !FILE_ID_PATTERN.test(fileId)) {
    throw new Error(
      `Invalid file ID: "${fileId}". File IDs contain only letters, numbers, hyphens, and underscores.`,
    );
  }
}

// ─── Client management ─────────────────────────────────────────────────────

async function refreshIfNeeded(account: AccountInfo): Promise<drive_v3.Drive> {
  checkRateLimit(account.id);
  const auth = createAuthenticatedClient(account.tokens);

  auth.on("tokens", async (newTokens) => {
    account.tokens = { ...account.tokens, ...newTokens };
    await saveAccount(account);
  });

  await auth.getAccessToken();
  return google.drive({ version: "v3", auth });
}

function toDriveFile(
  file: drive_v3.Schema$File,
  accountLabel: string,
): DriveFile {
  return {
    id: file.id || "",
    name: file.name || "Untitled",
    mimeType: file.mimeType || "application/octet-stream",
    size: file.size || undefined,
    modifiedTime: file.modifiedTime || undefined,
    webViewLink: file.webViewLink || undefined,
    account: accountLabel,
  };
}

// ─── File operations ────────────────────────────────────────────────────────

export async function listFiles(
  accountId: string,
  folderId?: string,
  pageSize: number = 20,
  pageToken?: string,
): Promise<{ files: DriveFile[]; nextPageToken?: string }> {
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account not found`);

  if (folderId) validateFileId(folderId);

  const drive = await refreshIfNeeded(account);

  let query = "trashed = false";
  if (folderId) {
    query += ` and '${sanitizeQueryValue(folderId)}' in parents`;
  }

  const res = await drive.files.list({
    q: query,
    pageSize: Math.min(Math.max(pageSize, 1), 100),
    pageToken,
    fields:
      "nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
    orderBy: "modifiedTime desc",
  });

  return {
    files: (res.data.files || []).map((f) => toDriveFile(f, account.label)),
    nextPageToken: res.data.nextPageToken || undefined,
  };
}

export interface SearchResults {
  results: SearchResult[];
  errors: Array<{ account: string; accountLabel: string; error: string }>;
}

export async function searchFiles(
  query: string,
  accountIds?: string[],
): Promise<SearchResults> {
  const allAccounts = await getAllAccounts();
  const targets = accountIds
    ? allAccounts.filter((a) => accountIds.includes(a.id))
    : allAccounts;

  if (targets.length === 0) {
    if (accountIds && accountIds.length > 0) {
      throw new Error(
        `None of the specified account IDs were found. Use list_accounts to see available accounts.`,
      );
    }
    throw new Error("No accounts configured. Add an account first.");
  }

  const settled = await Promise.allSettled(
    targets.map(async (account) => {
      const drive = await refreshIfNeeded(account);
      const escapedQuery = sanitizeQueryValue(query);

      const res = await drive.files.list({
        q: `fullText contains '${escapedQuery}' and trashed = false`,
        pageSize: 10,
        fields:
          "files(id, name, mimeType, size, modifiedTime, webViewLink)",
        orderBy: "modifiedTime desc",
      });

      return {
        account: account.id,
        accountLabel: account.label,
        files: (res.data.files || []).map((f) =>
          toDriveFile(f, account.label),
        ),
      };
    }),
  );

  const results: SearchResult[] = [];
  const errors: SearchResults["errors"] = [];

  settled.forEach((s, i) => {
    if (s.status === "fulfilled") {
      results.push(s.value);
    } else {
      errors.push({
        account: targets[i].id,
        accountLabel: targets[i].label,
        error: sanitizeErrorMessage(s.reason),
      });
    }
  });

  return { results, errors };
}

// Maximum size we'll export from Google Workspace files (5 MB).
// This protects against giant Docs eating the entire token budget.
const MAX_EXPORT_SIZE = 5 * 1024 * 1024;

export async function readFile(
  accountId: string,
  fileId: string,
): Promise<{ content: string; name: string; mimeType: string }> {
  validateFileId(fileId);
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account not found`);

  const drive = await refreshIfNeeded(account);

  const meta = await drive.files.get({
    fileId,
    fields: "id, name, mimeType, size",
  });

  const mimeType = meta.data.mimeType || "";
  const name = meta.data.name || "Untitled";

  const exportMimeMap: Record<string, string> = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.drawing": "image/svg+xml",
  };

  if (exportMimeMap[mimeType]) {
    const res = await drive.files.export(
      { fileId, mimeType: exportMimeMap[mimeType] },
      { responseType: "text" },
    );
    const content = String(res.data);
    if (content.length > MAX_EXPORT_SIZE) {
      return {
        content:
          content.slice(0, MAX_EXPORT_SIZE) +
          `\n\n[Content truncated at ${(MAX_EXPORT_SIZE / 1024 / 1024).toFixed(0)}MB. ` +
          `Full file available via Google Drive.]`,
        name,
        mimeType: exportMimeMap[mimeType],
      };
    }
    return { content, name, mimeType: exportMimeMap[mimeType] };
  }

  const sizeBytes = parseInt(meta.data.size || "0", 10);
  const MAX_DOWNLOAD_SIZE = 10 * 1024 * 1024;

  if (sizeBytes > MAX_DOWNLOAD_SIZE) {
    return {
      content: `[File too large to read inline: ${(sizeBytes / 1024 / 1024).toFixed(1)}MB. Use the file's webViewLink to access it in browser.]`,
      name,
      mimeType,
    };
  }

  const res = await drive.files.get(
    { fileId, alt: "media" },
    { responseType: "text" },
  );

  return { content: String(res.data), name, mimeType };
}

export async function getFileMetadata(
  accountId: string,
  fileId: string,
): Promise<DriveFile> {
  validateFileId(fileId);
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account not found`);

  const drive = await refreshIfNeeded(account);

  const res = await drive.files.get({
    fileId,
    fields: "id, name, mimeType, size, modifiedTime, webViewLink",
  });

  return toDriveFile(res.data, account.label);
}
