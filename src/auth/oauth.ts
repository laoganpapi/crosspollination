import { google } from "googleapis";
import { createServer } from "node:http";
import { URL } from "node:url";
import { randomBytes } from "node:crypto";
import type { AccountInfo } from "../types.js";
import { saveAccount, findAccountByEmail } from "./store.js";

const SCOPES = [
  "https://www.googleapis.com/auth/drive.readonly",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
];

function getOAuthClient(port: number) {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    throw new Error(
      "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set. " +
        "Create OAuth credentials at https://console.cloud.google.com/apis/credentials",
    );
  }

  return new google.auth.OAuth2(
    clientId,
    clientSecret,
    `http://localhost:${port}/oauth/callback`,
  );
}

export async function authenticateAccount(
  label: string,
): Promise<AccountInfo> {
  const port = parseInt(process.env.OAUTH_CALLBACK_PORT || "3847", 10);
  const oauth2Client = getOAuthClient(port);
  const state = randomBytes(16).toString("hex");

  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    state,
    prompt: "consent",
  });

  return new Promise((resolve, reject) => {
    const server = createServer(async (req, res) => {
      try {
        if (!req.url?.startsWith("/oauth/callback")) {
          res.writeHead(404);
          res.end("Not found");
          return;
        }

        const url = new URL(req.url, `http://localhost:${port}`);
        const code = url.searchParams.get("code");
        const returnedState = url.searchParams.get("state");
        const error = url.searchParams.get("error");

        if (error) {
          res.writeHead(400);
          res.end(`Authorization denied: ${error}`);
          server.close();
          reject(new Error(`OAuth error: ${error}`));
          return;
        }

        if (returnedState !== state) {
          res.writeHead(400);
          res.end("State mismatch — possible CSRF attack. Aborting.");
          server.close();
          reject(new Error("OAuth state mismatch"));
          return;
        }

        if (!code) {
          res.writeHead(400);
          res.end("No authorization code received");
          server.close();
          reject(new Error("No auth code"));
          return;
        }

        const { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);

        const oauth2 = google.oauth2({ version: "v2", auth: oauth2Client });
        const { data: userInfo } = await oauth2.userinfo.get();

        if (!userInfo.email) {
          res.writeHead(500);
          res.end("Could not retrieve email from Google account");
          server.close();
          reject(new Error("No email in user info"));
          return;
        }

        const existing = await findAccountByEmail(userInfo.email);
        const accountId =
          existing?.id || randomBytes(8).toString("hex");

        const account: AccountInfo = {
          id: accountId,
          email: userInfo.email,
          label: label || userInfo.email,
          tokens,
          addedAt: new Date().toISOString(),
        };

        await saveAccount(account);

        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(`
          <!DOCTYPE html>
          <html>
          <body style="font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f0f0;">
            <div style="text-align: center; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
              <h1 style="color: #1a73e8;">Connected!</h1>
              <p><strong>${userInfo.email}</strong> has been linked as <strong>"${account.label}"</strong></p>
              <p style="color: #666;">You can close this window and return to Claude.</p>
            </div>
          </body>
          </html>
        `);

        server.close();
        resolve(account);
      } catch (err) {
        res.writeHead(500);
        res.end("Internal error during authentication");
        server.close();
        reject(err);
      }
    });

    server.listen(port, () => {
      console.error(
        `\n🔗 Open this URL to authenticate your Google account:\n\n${authUrl}\n`,
      );
    });

    server.on("error", (err) => {
      reject(
        new Error(
          `Could not start OAuth callback server on port ${port}: ${err.message}`,
        ),
      );
    });

    setTimeout(() => {
      server.close();
      reject(new Error("Authentication timed out after 5 minutes"));
    }, 300_000);
  });
}

export function createAuthenticatedClient(tokens: import("google-auth-library").Credentials) {
  const port = parseInt(process.env.OAUTH_CALLBACK_PORT || "3847", 10);
  const client = getOAuthClient(port);
  client.setCredentials(tokens);
  return client;
}
