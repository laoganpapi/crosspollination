import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { readFile, writeFile, mkdir, rename, unlink } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { AccountInfo, AccountStore, EncryptedPayload } from "../types.js";

const ALGORITHM = "aes-256-gcm";
const STORE_DIR = join(
  process.env.CROSSPOLLINATION_DATA_DIR || join(homedir(), ".crosspollination"),
);
const STORE_FILE = join(STORE_DIR, "accounts.enc.json");

// ─── Encryption key management ──────────────────────────────────────────────

let cachedKey: Buffer | null = null;

function getEncryptionKey(): Buffer {
  if (cachedKey) return cachedKey;
  const key = process.env.ENCRYPTION_KEY;
  if (!key || key.length !== 64 || !/^[0-9a-fA-F]{64}$/.test(key)) {
    throw new Error(
      "ENCRYPTION_KEY must be a 64-character hex string (32 bytes). " +
        'Generate one with: node -e "console.log(require(\'crypto\').randomBytes(32).toString(\'hex\'))"',
    );
  }
  cachedKey = Buffer.from(key, "hex");
  return cachedKey;
}

/** Call at startup to fail fast if the key is missing or malformed. */
export function validateEncryptionKey(): void {
  getEncryptionKey();
}

// ─── Crypto primitives ─────────────────────────────────────────────────────

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

// ─── File I/O with atomic writes ────────────────────────────────────────────

// Serialize all store writes through a single promise chain to prevent
// concurrent read-modify-write races.
let writeQueue: Promise<void> = Promise.resolve();

async function loadStore(): Promise<AccountStore> {
  try {
    const raw = await readFile(STORE_FILE, "utf8");
    return JSON.parse(raw) as AccountStore;
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return { version: 1, accounts: {} };
    }
    throw err;
  }
}

async function saveStoreAtomic(store: AccountStore): Promise<void> {
  await mkdir(STORE_DIR, { recursive: true, mode: 0o700 });
  // Write to a temp file then atomically rename — prevents corruption if
  // the process is killed mid-write.
  const tmpFile = `${STORE_FILE}.${randomBytes(4).toString("hex")}.tmp`;
  await writeFile(tmpFile, JSON.stringify(store, null, 2), { mode: 0o600 });
  try {
    await rename(tmpFile, STORE_FILE);
  } catch (err) {
    // Clean up the temp file if rename fails
    await unlink(tmpFile).catch(() => {});
    throw err;
  }
}

/** Run a read-modify-write cycle under a serialized queue. */
async function withStore(
  fn: (store: AccountStore) => AccountStore | Promise<AccountStore>,
): Promise<AccountStore> {
  let result!: AccountStore;
  writeQueue = writeQueue.then(async () => {
    const store = await loadStore();
    result = await fn(store);
    await saveStoreAtomic(result);
  });
  await writeQueue;
  return result;
}

// ─── Public API ─────────────────────────────────────────────────────────────

export async function saveAccount(account: AccountInfo): Promise<void> {
  const serialized = JSON.stringify(account);
  await withStore((store) => {
    store.accounts[account.id] = encrypt(serialized);
    return store;
  });
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
  let existed = false;
  await withStore((store) => {
    existed = accountId in store.accounts;
    if (existed) {
      delete store.accounts[accountId];
    }
    return store;
  });
  return existed;
}

export async function findAccountByEmail(
  email: string,
): Promise<AccountInfo | null> {
  const accounts = await getAllAccounts();
  return accounts.find((a) => a.email === email) || null;
}
