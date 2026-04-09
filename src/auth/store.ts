import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import type { AccountInfo, AccountStore, EncryptedPayload } from "../types.js";

const ALGORITHM = "aes-256-gcm";
const STORE_DIR = join(
  process.env.CROSSPOLLINATION_DATA_DIR ||
    join(process.env.HOME || "~", ".crosspollination"),
);
const STORE_FILE = join(STORE_DIR, "accounts.enc.json");

function getEncryptionKey(): Buffer {
  const key = process.env.ENCRYPTION_KEY;
  if (!key || key.length !== 64) {
    throw new Error(
      "ENCRYPTION_KEY must be a 64-character hex string (32 bytes). " +
        'Generate one with: node -e "console.log(require(\'crypto\').randomBytes(32).toString(\'hex\'))"',
    );
  }
  return Buffer.from(key, "hex");
}

function encrypt(data: string): EncryptedPayload {
  const key = getEncryptionKey();
  const iv = randomBytes(12);
  const cipher = createCipheriv(ALGORITHM, key, iv);

  let encrypted = cipher.update(data, "utf8", "hex");
  encrypted += cipher.final("hex");
  const tag = cipher.getAuthTag();

  return {
    iv: iv.toString("hex"),
    tag: tag.toString("hex"),
    data: encrypted,
  };
}

function decrypt(payload: EncryptedPayload): string {
  const key = getEncryptionKey();
  const iv = Buffer.from(payload.iv, "hex");
  const tag = Buffer.from(payload.tag, "hex");
  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(tag);

  let decrypted = decipher.update(payload.data, "hex", "utf8");
  decrypted += decipher.final("utf8");
  return decrypted;
}

async function loadStore(): Promise<AccountStore> {
  if (!existsSync(STORE_FILE)) {
    return { version: 1, accounts: {} };
  }
  const raw = await readFile(STORE_FILE, "utf8");
  return JSON.parse(raw) as AccountStore;
}

async function saveStore(store: AccountStore): Promise<void> {
  if (!existsSync(STORE_DIR)) {
    await mkdir(STORE_DIR, { recursive: true, mode: 0o700 });
  }
  await writeFile(STORE_FILE, JSON.stringify(store, null, 2), {
    mode: 0o600,
  });
}

export async function saveAccount(account: AccountInfo): Promise<void> {
  const store = await loadStore();
  const serialized = JSON.stringify(account);
  store.accounts[account.id] = encrypt(serialized);
  await saveStore(store);
}

export async function getAccount(
  accountId: string,
): Promise<AccountInfo | null> {
  const store = await loadStore();
  const payload = store.accounts[accountId];
  if (!payload) return null;
  const decrypted = decrypt(payload);
  return JSON.parse(decrypted) as AccountInfo;
}

export async function getAllAccounts(): Promise<AccountInfo[]> {
  const store = await loadStore();
  const accounts: AccountInfo[] = [];
  for (const payload of Object.values(store.accounts)) {
    const decrypted = decrypt(payload);
    accounts.push(JSON.parse(decrypted) as AccountInfo);
  }
  return accounts;
}

export async function removeAccount(accountId: string): Promise<boolean> {
  const store = await loadStore();
  if (!store.accounts[accountId]) return false;
  delete store.accounts[accountId];
  await saveStore(store);
  return true;
}

export async function findAccountByEmail(
  email: string,
): Promise<AccountInfo | null> {
  const accounts = await getAllAccounts();
  return accounts.find((a) => a.email === email) || null;
}
