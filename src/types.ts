import type { Credentials } from "google-auth-library";

export interface AccountInfo {
  id: string;
  email: string;
  label: string;
  tokens: Credentials;
  addedAt: string;
}

export interface EncryptedPayload {
  iv: string;
  tag: string;
  data: string;
}

export interface AccountStore {
  version: number;
  accounts: Record<string, EncryptedPayload>;
}

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  modifiedTime?: string;
  webViewLink?: string;
  account: string;
}

export interface SearchResult {
  account: string;
  accountLabel: string;
  files: DriveFile[];
}
