import type { Context } from "@netlify/functions";
import { Bot, InlineKeyboard } from "grammy";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { Octokit } from "@octokit/rest";

// Environment variables
const TELEGRAM_BOT_TOKEN = Netlify.env.get("TELEGRAM_BOT_TOKEN") || "";
const GOOGLE_API_KEY = Netlify.env.get("GOOGLE_API_KEY") || "";
const GITHUB_TOKEN = Netlify.env.get("GITHUB_TOKEN") || "";
const GITHUB_REPOSITORY = Netlify.env.get("GITHUB_REPOSITORY") || "";

// Initialize clients
const genai = new GoogleGenerativeAI(GOOGLE_API_KEY);
const octokit = new Octokit({ auth: GITHUB_TOKEN });

// Prompts
const IMPROVE_PROMPT = `You are a helpful editor. Improve the following text for clarity, flow, and grammar. 
Keep the tone natural and authentic. Do not be overly formal. 
Output ONLY the improved text. No preamble.`;

const METADATA_PROMPT = `Analyze the following blog post draft. 
Extract a suitable Title and the Date of the event/post if mentioned. 
If no date is mentioned, use today's date ({today}).
Return ONLY a JSON object with keys: "title" (string), "date" (YYYY-MM-DD string).
Text:
`;

// Store draft text temporarily (in production, use a database or session storage)
const drafts = new Map<number, string>();

export default async (req: Request, context: Context) => {
    // Only accept POST requests
    if (req.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
    }

    try {
        const update = await req.json();

        // Handle text messages (new drafts)
        if (update.message?.text) {
            const chatId = update.message.chat.id;
            const originalText = update.message.text;

            // Skip commands
            if (originalText.startsWith("/")) {
                if (originalText === "/start") {
                    await sendMessage(chatId, "Hi! Send me a rough draft, and I'll help you polish and publish it to your blog.");
                }
                return new Response("OK", { status: 200 });
            }

            // Store original draft
            drafts.set(chatId, originalText);

            // Improve text with Gemini
            const model = genai.getGenerativeModel({ model: "gemini-pro" });
            const result = await model.generateContent(`${IMPROVE_PROMPT}\n\n${originalText}`);
            const improvedText = result.response.text();

            // Send improved version with buttons
            const keyboard = new InlineKeyboard()
                .text("Do again 🔄", "retry")
                .text("Cancel ❌", "cancel")
                .row()
                .text("Post it ✅", "post");

            await sendMessage(chatId, improvedText, keyboard);
        }

        // Handle button callbacks
        if (update.callback_query) {
            const callbackQuery = update.callback_query;
            const chatId = callbackQuery.message.chat.id;
            const messageId = callbackQuery.message.message_id;
            const action = callbackQuery.data;
            const currentText = callbackQuery.message.text;

            // Acknowledge callback
            await answerCallback(callbackQuery.id);

            if (action === "cancel") {
                drafts.delete(chatId);
                await editMessage(chatId, messageId, "❌ Draft discarded.");
                return new Response("OK", { status: 200 });
            }

            if (action === "retry") {
                const originalText = drafts.get(chatId);
                if (!originalText) {
                    await editMessage(chatId, messageId, "Error: Original draft not found.");
                    return new Response("OK", { status: 200 });
                }

                // Re-improve with slight variation
                const model = genai.getGenerativeModel({ model: "gemini-pro" });
                const result = await model.generateContent(`${IMPROVE_PROMPT} Write it slightly differently this time.\n\n${originalText}`);
                const newText = result.response.text();

                const keyboard = new InlineKeyboard()
                    .text("Do again 🔄", "retry")
                    .text("Cancel ❌", "cancel")
                    .row()
                    .text("Post it ✅", "post");

                await editMessage(chatId, messageId, newText, keyboard);
            }

            if (action === "post") {
                await editMessage(chatId, messageId, `${currentText}\n\n⏳ Publishing...`);

                try {
                    // Extract metadata
                    const model = genai.getGenerativeModel({ model: "gemini-pro" });
                    const today = new Date().toISOString().split('T')[0];
                    const metadataResult = await model.generateContent(
                        METADATA_PROMPT.replace("{today}", today) + currentText
                    );

                    let metadata: { title: string; date: string };
                    try {
                        const jsonText = metadataResult.response.text()
                            .replace(/```json\n?/g, "")
                            .replace(/```\n?/g, "")
                            .trim();
                        metadata = JSON.parse(jsonText);
                    } catch {
                        metadata = { title: "Untitled Post", date: today };
                    }

                    // Create markdown file content
                    const fileContent = `Title: ${metadata.title}\nDate: ${metadata.date}\n\n${currentText}`;

                    // Generate filename
                    const slug = metadata.title
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")
                        .substring(0, 50);
                    const filename = `content/${metadata.date}-${slug}.md`;

                    // Commit to GitHub
                    const [owner, repo] = GITHUB_REPOSITORY.split("/");
                    await octokit.repos.createOrUpdateFileContents({
                        owner,
                        repo,
                        path: filename,
                        message: `New post via Bot: ${metadata.title}`,
                        content: Buffer.from(fileContent).toString("base64"),
                        branch: "main",
                    });

                    await editMessage(
                        chatId,
                        messageId,
                        `${currentText}\n\n✅ Published!\nDate: ${metadata.date}\nTitle: ${metadata.title}\n\n(Rebuild triggered)`
                    );

                    drafts.delete(chatId);
                } catch (error) {
                    await editMessage(chatId, messageId, `${currentText}\n\n❌ Publish failed: ${error}`);
                }
            }
        }

        return new Response("OK", { status: 200 });
    } catch (error) {
        console.error("Error:", error);
        return new Response("Internal Server Error", { status: 500 });
    }
};

// Helper functions
async function sendMessage(chatId: number, text: string, keyboard?: InlineKeyboard) {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            chat_id: chatId,
            text,
            reply_markup: keyboard ? keyboard : undefined,
        }),
    });
}

async function editMessage(chatId: number, messageId: number, text: string, keyboard?: InlineKeyboard) {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText`;
    await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            chat_id: chatId,
            message_id: messageId,
            text,
            reply_markup: keyboard ? keyboard : undefined,
        }),
    });
}

async function answerCallback(callbackQueryId: string) {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/answerCallbackQuery`;
    await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ callback_query_id: callbackQueryId }),
    });
}
