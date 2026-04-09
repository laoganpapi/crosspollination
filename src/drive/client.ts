import { google, type drive_v3 } from "googleapis";
import type { Credentials } from "google-auth-library";
import { createAuthenticatedClient } from "../auth/oauth.js";
import { getAllAccounts, getAccount, saveAccount } from "../auth/store.js";
import type { AccountInfo, DriveFile, SearchResult } from "../types.js";

function buildDriveClient(tokens: Credentials): drive_v3.Drive {
  const auth = createAuthenticatedClient(tokens);
  return google.drive({ version: "v3", auth });
}

async function refreshIfNeeded(account: AccountInfo): Promise<drive_v3.Drive> {
  const auth = createAuthenticatedClient(account.tokens);

  auth.on("tokens", async (newTokens) => {
    account.tokens = { ...account.tokens, ...newTokens };
    await saveAccount(account);
  });

  // Force a credentials check to trigger refresh if expired
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

export async function listFiles(
  accountId: string,
  folderId?: string,
  pageSize: number = 20,
  pageToken?: string,
): Promise<{ files: DriveFile[]; nextPageToken?: string }> {
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account ${accountId} not found`);

  const drive = await refreshIfNeeded(account);

  let query = "trashed = false";
  if (folderId) {
    query += ` and '${folderId}' in parents`;
  }

  const res = await drive.files.list({
    q: query,
    pageSize,
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

export async function searchFiles(
  query: string,
  accountIds?: string[],
): Promise<SearchResult[]> {
  const allAccounts = await getAllAccounts();
  const targets = accountIds
    ? allAccounts.filter((a) => accountIds.includes(a.id))
    : allAccounts;

  if (targets.length === 0) {
    throw new Error("No accounts configured. Add an account first.");
  }

  const results = await Promise.allSettled(
    targets.map(async (account) => {
      const drive = await refreshIfNeeded(account);
      const escapedQuery = query.replace(/'/g, "\\'");

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
        files: (res.data.files || []).map((f) => toDriveFile(f, account.label)),
      };
    }),
  );

  return results
    .filter(
      (r): r is PromiseFulfilledResult<SearchResult> =>
        r.status === "fulfilled",
    )
    .map((r) => r.value);
}

export async function readFile(
  accountId: string,
  fileId: string,
): Promise<{ content: string; name: string; mimeType: string }> {
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account ${accountId} not found`);

  const drive = await refreshIfNeeded(account);

  // Get file metadata first
  const meta = await drive.files.get({
    fileId,
    fields: "id, name, mimeType, size",
  });

  const mimeType = meta.data.mimeType || "";
  const name = meta.data.name || "Untitled";

  // Google Workspace files need to be exported
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
    return { content: String(res.data), name, mimeType: exportMimeMap[mimeType] };
  }

  // For regular files, download content
  const sizeBytes = parseInt(meta.data.size || "0", 10);
  const MAX_SIZE = 10 * 1024 * 1024; // 10MB limit for text content

  if (sizeBytes > MAX_SIZE) {
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
  const account = await getAccount(accountId);
  if (!account) throw new Error(`Account ${accountId} not found`);

  const drive = await refreshIfNeeded(account);

  const res = await drive.files.get({
    fileId,
    fields: "id, name, mimeType, size, modifiedTime, webViewLink",
  });

  return toDriveFile(res.data, account.label);
}
