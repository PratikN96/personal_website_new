import type { Context } from "@netlify/functions";
import { Bot } from "grammy";

const REMINDER_BOT_TOKEN = process.env["REMINDER_BOT_TOKEN"] || "";
const MY_CHAT_ID = process.env["MY_CHAT_ID"] || "";

export default async (req: Request, context: Context) => {
    if (!REMINDER_BOT_TOKEN || !MY_CHAT_ID) {
        return new Response(
            JSON.stringify({
                error: "Missing environment variables",
                hasToken: !!REMINDER_BOT_TOKEN,
                hasChatId: !!MY_CHAT_ID
            }),
            {
                status: 500,
                headers: { "Content-Type": "application/json" }
            }
        );
    }

    const bot = new Bot(REMINDER_BOT_TOKEN);

    try {
        // Send test message
        await bot.api.sendMessage(
            MY_CHAT_ID,
            "🧪 **Test Successful!**\n\n✅ Your reminder bot is working correctly.\n✅ Chat ID is configured.\n✅ Bot token is valid.\n\nYou will receive reminders on:\n• Jan 16 - Anniversary\n• Jan 26 - Birthday",
            { parse_mode: "Markdown" }
        );

        return new Response(
            JSON.stringify({
                success: true,
                message: "Test message sent to Telegram!",
                chatId: MY_CHAT_ID
            }),
            {
                status: 200,
                headers: { "Content-Type": "application/json" }
            }
        );
    } catch (error) {
        return new Response(
            JSON.stringify({
                error: "Failed to send message",
                details: String(error)
            }),
            {
                status: 500,
                headers: { "Content-Type": "application/json" }
            }
        );
    }
};
