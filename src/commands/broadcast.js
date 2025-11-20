import { getAllUserIds } from "../functions/mongodb.js";

const ADMIN_USER_ID = 5850931697;

function extractBroadcastText(text = "") {
  const parts = text.split(/\s+/, 2);
  if (parts.length < 2) return "";
  return text.slice(text.indexOf(parts[1])).trim();
}

export function registerBroadcast(bot) {
  bot.command("brd", async (ctx) => {
    if (!ctx.from || ctx.from.id !== ADMIN_USER_ID) {
      await ctx.reply("❌ You are not authorized to use this command.");
      return;
    }

    const broadcastText = extractBroadcastText(ctx.message?.text || "");
    if (!broadcastText) {
      await ctx.reply(
        "Usage: /brd your-message-here\nExample: /brd The service will be down for maintenance tonight."
      );
      return;
    }

    const userIds = await getAllUserIds();
    const recipients = [...new Set(userIds)];
    if (!recipients.length) {
      await ctx.reply("No registered users to broadcast to.");
      return;
    }

    let sent = 0;
    let failed = 0;
    for (const userId of recipients) {
      try {
        await ctx.telegram.sendMessage(userId, broadcastText, { parse_mode: undefined });
        sent += 1;
      } catch (err) {
        failed += 1;
        console.warn("Failed to deliver broadcast to", userId, err);
      }
    }

    let summary = `Broadcast delivered to ${sent} user(s).`;
    if (failed) summary += ` Failed to deliver to ${failed} user(s).`;
    await ctx.reply(summary);
  });
}
