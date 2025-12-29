import { schedule } from "@netlify/functions";
import { Bot } from "grammy";

// Environment variables
const REMINDER_BOT_TOKEN = process.env["REMINDER_BOT_TOKEN"] || "";
const MY_CHAT_ID = process.env["MY_CHAT_ID"] || "";

// Initialize Bot
const bot = new Bot(REMINDER_BOT_TOKEN);

// Events Configuration
const EVENTS = [
    { day: 16, month: 0, message: "🎉 Happy Anniversary Mom & Papa! ❤️" }, // Month is 0-indexed (0 = Jan)
    { day: 26, month: 0, message: "🎂 Happy Birthday to me! 🥳" },
];

const checkAndSendReminders = async () => {
    if (!REMINDER_BOT_TOKEN || !MY_CHAT_ID) {
        console.error("Missing REMINDER_BOT_TOKEN or MY_CHAT_ID");
        return;
    }

    // Get current date in IST (Indian Standard Time)
    const now = new Date();
    const istDate = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));

    const currentDay = istDate.getDate();
    const currentMonth = istDate.getMonth(); // 0-11

    console.log(`Checking reminders for date: ${istDate.toDateString()} (Day: ${currentDay}, Month: ${currentMonth})`);

    for (const event of EVENTS) {
        if (event.day === currentDay && event.month === currentMonth) {
            console.log(`Match found! Sending message: ${event.message}`);
            try {
                await bot.api.sendMessage(MY_CHAT_ID, event.message);
                console.log("Message sent successfully.");
            } catch (error) {
                console.error("Failed to send message:", error);
            }
        }
    }
};

// Schedule: Runs every day at 4:30 AM UTC (which is 10:00 AM IST)
export const handler = schedule("30 4 * * *", async (event) => {
    try {
        await checkAndSendReminders();
    } catch (error) {
        console.error("Error in reminder bot:", error);
    }
    return {
        statusCode: 200,
    };
});
