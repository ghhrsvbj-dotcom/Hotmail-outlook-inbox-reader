import dotenv from "dotenv";
import { Telegraf, Markup } from "telegraf";
import escapeHtml from "escape-html";
import { registerStart } from "./commands/start.js";
import { registerBroadcast } from "./commands/broadcast.js";
import { fetchInboxPreview } from "./Api/hotmailoutlookapi.js";
import { fetchInboxSummary, formatSummary } from "./Api/edu.js";

dotenv.config();

const TELEGRAM_BOT_TOKEN = "8293805278:AAGSEFsHqUPu5AGG7Rjhy430bqd2xzGsWZw";
const DEFAULT_MESSAGE_COUNT = parseInt(process.env.MESSAGE_COUNT || "40", 10);

const DATA_PATTERN = /(?<email>[A-Za-z0-9._%+-]+@(hotmail|outlook)\.[A-Za-z0-9.-]+)\|(?<password>[^|]*)\|(?<refresh>M\.[^|]+)\|(?<client>[0-9a-fA-F-]{36})/;
const EDU_PATTERN = /^(?<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)\|(?<password>[^|\s]+)\s*$/;

function parseCredentials(raw) {
  if (!raw) return null;
  const match = DATA_PATTERN.exec(raw.trim());
  if (!match || !match.groups) return null;
  return {
    email: match.groups.email,
    refresh: match.groups.refresh,
    client: match.groups.client,
  };
}

function formatTimestamp(date) {
  if (!date) return "Unknown";
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleString();
}

async function handleEdu(ctx, email, password) {
  const progress = await ctx.reply("Starting Gmail fetch... ⌛");
  try {
    const summary = await fetchInboxSummary(email, { password, headless: true });
    const summaryData = formatSummary(summary);
    const codes = summaryData.codes || [];
    const duration = summaryData.duration;
    const errors = summaryData.errors || [];

    if (codes.length) {
      const codeLines = codes.map((code) => `Facebook confirmation code : <code>${escapeHtml(String(code))}</code>`).join("\n");
      const timeText = duration ? `Time : ${duration.toFixed(2)}s` : "Time : N/A";
      const messageText = `✨OTP FOUND  ✨\n\n${codeLines}\n\n${escapeHtml(timeText)}`;
      await ctx.telegram.editMessageText(progress.chat.id, progress.message_id, undefined, messageText, { parse_mode: "HTML" });
    } else if (errors.length) {
      const warnings = errors.map((err) => `- ${err}`).join("\n");
      await ctx.telegram.editMessageText(
        progress.chat.id,
        progress.message_id,
        undefined,
        `No Facebook confirmation codes were found.\n\nWarnings:\n${warnings}`,
        { parse_mode: undefined }
      );
    } else {
      await ctx.telegram.editMessageText(progress.chat.id, progress.message_id, undefined, "No Facebook confirmation codes were found.");
    }
  } catch (err) {
    await ctx.telegram.editMessageText(
      progress.chat.id,
      progress.message_id,
      undefined,
      `An error occurred while fetching the inbox: ${err}`
    );
  }
}

async function handleHotmail(ctx, text) {
  const creds = parseCredentials(text);
  if (!creds) {
    await ctx.reply(
      "❌ Unable to parse credentials. Ensure the format is email|password|refresh_token|client_id and the email is Hotmail/Outlook."
    );
    return;
  }

  try {
    const previewData = await fetchInboxPreview(creds.email, creds.refresh, creds.client, {
      messageCount: DEFAULT_MESSAGE_COUNT,
    });
    const status = previewData.status;
    if (status !== "found" || !previewData.otp) {
      if (status === "no_otp") {
        const subject = previewData.subject || "(no subject)";
        await ctx.reply(`⚠️ Latest Facebook email found but no OTP detected.\nSubject: ${escapeHtml(subject)}`);
      } else {
        await ctx.reply("❌ No Facebook OTP emails found.");
      }
      return;
    }

    const formattedTime = formatTimestamp(previewData.receivedAt);
    const elapsedText = `${(previewData.elapsed_seconds || 0).toFixed(2)} seconds`;
    const otp = previewData.otp;
    const messageText =
      "✨FACEBOOK OTP FOUND ✨\n\n" +
      `✉️ Email : ${escapeHtml(creds.email)}\n` +
      `🔐 OTP : <code>${escapeHtml(String(otp))}</code>\n` +
      `🕒 Time : ${escapeHtml(formattedTime)}\n` +
      `⏱️ Time taken : ${elapsedText}`;

    const keyboard = Markup.inlineKeyboard([[Markup.button.callback("Copy OTP", `copy:${otp}`)]]);

    await ctx.reply(messageText, { parse_mode: "HTML", reply_markup: keyboard.reply_markup, disable_web_page_preview: true });
  } catch (err) {
    await ctx.reply(`❌ Error: ${err}`);
  }
}

function registerCopyHandler(bot) {
  bot.action(/copy:(.+)/, async (ctx) => {
    await ctx.answerCbQuery("OTP copied", { show_alert: false });
  });
}

function isCommandMessage(text = "") {
  return text.trim().startsWith("/");
}

async function main() {
  if (!TELEGRAM_BOT_TOKEN) throw new Error("TELEGRAM_BOT_TOKEN environment variable is required.");
  const bot = new Telegraf(TELEGRAM_BOT_TOKEN, { telegram: { parse_mode: "HTML" } });

  registerStart(bot);
  registerBroadcast(bot);
  registerCopyHandler(bot);

  bot.on("text", async (ctx) => {
    const text = ctx.message.text.trim();
    if (isCommandMessage(text)) return;

    const eduMatch = text.match(EDU_PATTERN);
    if (eduMatch && eduMatch.groups) {
      await handleEdu(ctx, eduMatch.groups.email, eduMatch.groups.password);
      return;
    }

    await handleHotmail(ctx, text);
  });

  await bot.launch();
  console.log("Bot is running...");
}

main().catch((err) => {
  console.error("Failed to start bot", err);
  process.exit(1);
});
