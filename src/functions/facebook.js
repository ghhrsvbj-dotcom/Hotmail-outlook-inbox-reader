import he from "he";
import { IGNORED_OTPS } from "./ignoredOtp.js";

const FB_CODE_WITH_PREFIX = /FB-(\d{5,8})\b/g;
const FB_CODE_STANDALONE = /\b(\d{5,8})\b/g;

const confirmationKeywords = [
  "confirmation code:",
  "your code:",
  "your confirmation code:",
  "here's your confirmation code:",
  "verification code:"
];

function extractOtp(text = "") {
  const matchesWithPrefix = Array.from(text.matchAll(FB_CODE_WITH_PREFIX));
  for (const match of matchesWithPrefix) {
    const candidate = match[1];
    if (!IGNORED_OTPS.has(candidate)) return candidate;
  }

  const matchesStandalone = Array.from(text.matchAll(FB_CODE_STANDALONE));
  if (!matchesStandalone.length) return null;

  const lower = text.toLowerCase();
  for (const keyword of confirmationKeywords) {
    const keywordPos = lower.indexOf(keyword);
    if (keywordPos === -1) continue;
    for (const match of matchesStandalone) {
      if (match.index !== undefined && match.index > keywordPos) {
        const candidate = match[1];
        if (!IGNORED_OTPS.has(candidate)) return candidate;
      }
    }
  }

  const candidates = matchesStandalone
    .map((m) => m[1])
    .filter((code) => !IGNORED_OTPS.has(code));
  if (candidates.length) return candidates.sort((a, b) => b.length - a.length)[0];
  return null;
}

function messageToText(msg) {
  if (!msg) return "";
  if (msg.text) return msg.text;
  if (msg.html) return he.decode(msg.html);
  return "";
}

export function parseFacebookEmail(rawMessage) {
  const subject = rawMessage.subject || "(no subject)";
  const textContent = messageToText(rawMessage.content);
  const otpFromSubject = extractOtp(subject);
  const otpFromBody = extractOtp(textContent);
  const otp = otpFromSubject || otpFromBody;

  return {
    otp,
    subject,
    receivedAt: rawMessage.date || null
  };
}

export function buildFacebookResult(messages) {
  if (!messages || !messages.length) {
    return { status: "no_emails", otp: null, subject: null, receivedAt: null };
  }

  for (const message of messages) {
    const parsed = parseFacebookEmail(message);
    if (parsed.otp) {
      return {
        status: "found",
        otp: parsed.otp,
        subject: parsed.subject,
        receivedAt: parsed.receivedAt
      };
    }
  }

  return {
    status: "no_otp",
    otp: null,
    subject: messages[0]?.subject || "(no subject)",
    receivedAt: null
  };
}
