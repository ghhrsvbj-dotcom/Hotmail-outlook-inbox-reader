import { Markup } from "telegraf";
import { saveUser } from "../functions/mongodb.js";

export function registerStart(bot) {
  bot.start(async (ctx) => {
    const user = ctx.from;
    if (user) {
      try {
        await saveUser(user.id, user.username, user.first_name);
      } catch (err) {
        console.warn("Failed to persist user", user.id, err);
      }
    }

    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback("🇧🇩 বাংলা", "lang:bn"), Markup.button.callback("🇬🇧 English", "lang:en")],
    ]);

    await ctx.reply(
      "🌐 Choose your language\nPlease pick how you'd like to use the bot.",
      keyboard
    );
  });

  bot.action("lang:bn", async (ctx) => {
    await ctx.answerCbQuery();
    const banglaText =
      "আমাদের বটে স্বাগতম!\n" +
      "আপনি এখন খুব সহজে আপনার Hotmail বা Outlook মেইল থেকে Facebook কোড পেতে পারেন —\n" +
      "শুধু আপনার মেইল পাঠান, আমরা সঙ্গে সঙ্গে কোডটা দিয়ে দেব।\n\n" +
      "🔐 অ্যাকাউন্ট তথ্য পাঠাতে এই ফরম্যাট ব্যবহার করুন:\n" +
      "<code>email|password|refresh_token|client_id</code>\n\n" +
      "শুধুমাত্র Hotmail/Outlook ঠিকানা গ্রহণ করা হবে।";
    await ctx.editMessageText(banglaText, { parse_mode: "HTML" });
  });

  bot.action("lang:en", async (ctx) => {
    await ctx.answerCbQuery();
    const englishText =
      "Welcome to our bot!\n" +
      "You can get your Hotmail or Outlook Facebook codes instantly —\n" +
      "just send your email, and we’ll fetch the code for you.\n\n" +
      "🔐 Send the account string in this format:\n" +
      "<code>email|password|refresh_token|client_id</code>\n\n" +
      "Only Hotmail/Outlook addresses are accepted.";
    await ctx.editMessageText(englishText, { parse_mode: "HTML" });
  });
}
