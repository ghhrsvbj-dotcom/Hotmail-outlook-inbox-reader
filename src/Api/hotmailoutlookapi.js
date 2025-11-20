import axios from "axios";
import { ImapFlow } from "imapflow";
import { simpleParser } from "mailparser";
import { buildFacebookResult } from "../functions/facebook.js";
import dotenv from "dotenv";

dotenv.config();

const TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token";
const IMAP_SERVER = "outlook.office365.com";

async function postFormWithRetries(url, data, maxRetries = 3) {
  let backoff = 750;
  let lastError;
  for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
    try {
      const response = await axios.post(url, new URLSearchParams(data), {
        headers: { "User-Agent": "hotmail-inbox-reader-node/1.0" },
      });
      if (response.status >= 500) throw new Error(`server error ${response.status}`);
      return response;
    } catch (err) {
      lastError = err;
      if (attempt === maxRetries) break;
      await new Promise((resolve) => setTimeout(resolve, backoff));
      backoff *= 2;
    }
  }
  throw new Error(`Token exchange failed after retries: ${lastError}`);
}

export async function getAccessToken(refreshToken, clientId, clientSecret) {
  if (!refreshToken || !clientId) throw new Error("Missing refresh token or client id");
  const data = {
    grant_type: "refresh_token",
    client_id: clientId,
    refresh_token: refreshToken,
  };
  if (clientSecret) data.client_secret = clientSecret;

  const response = await postFormWithRetries(TOKEN_URL, data);
  if (!response.data || !response.data.access_token) {
    throw new Error(`Token exchange failed: ${response.status}`);
  }
  return response.data;
}

async function fetchFacebookMessages(email, accessToken, maxMessages) {
  const client = new ImapFlow({
    host: IMAP_SERVER,
    port: 993,
    secure: true,
    auth: {
      user: email,
      accessToken,
      method: "XOAUTH2",
    },
  });

  await client.connect();
  try {
    await client.mailboxOpen("INBOX");
    const uids = await client.search({ from: "Facebook" });
    if (!uids.length) return [];
    const recent = uids.slice(-maxMessages).reverse();

    const messages = [];
    for await (const message of client.fetch(recent, {
      envelope: true,
      internalDate: true,
      source: true,
    })) {
      const parsed = await simpleParser(message.source);
      messages.push({
        subject: parsed.subject || message.envelope?.subject || "",
        date: message.internalDate,
        content: {
          text: parsed.text || "",
          html: parsed.html || "",
        },
      });
    }
    return messages;
  } finally {
    await client.logout();
  }
}

export async function fetchInboxPreview(email, refreshToken, clientId, { messageCount }) {
  const start = performance.now();
  const tokenData = await getAccessToken(refreshToken, clientId, process.env.CLIENT_SECRET);
  const accessToken = tokenData.access_token;
  if (!accessToken) throw new Error(`No access_token returned. Response: ${JSON.stringify(tokenData)}`);

  const messages = await fetchFacebookMessages(email, accessToken, Math.max(1, messageCount));
  const result = buildFacebookResult(messages);
  return { ...result, elapsed_seconds: (performance.now() - start) / 1000 };
}

export async function listLatestMessages(email, refreshToken, clientId, count = 10) {
  const tokenData = await getAccessToken(refreshToken, clientId, process.env.CLIENT_SECRET);
  const accessToken = tokenData.access_token;
  const messages = await fetchFacebookMessages(email, accessToken, Math.max(1, count));
  return messages;
}
