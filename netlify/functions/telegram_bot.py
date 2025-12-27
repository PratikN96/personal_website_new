import os
import json
import logging
import asyncio
import traceback
from datetime import datetime

# Configure logging immediately
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Safe Imports & Debugging ---
# We try to import dependencies. If they fail, we log it.
# This helps debug if Netlify actually installed the requirements.
deps_ok = True
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
    from telegram.constants import ParseMode
    import google.generativeai as genai
    from github import Github
except ImportError as e:
    deps_ok = False
    logger.error(f"CRITICAL: Dependency check failed. Are requirements.txt installed? Error: {e}")

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Initialize Gemini if available
if deps_ok and GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        logger.error(f"Gemini config error: {e}")

# --- Prompts ---
IMPROVE_PROMPT = """You are a helpful editor. Improve the following text for clarity, flow, and grammar. 
Keep the tone natural and authentic. Do not be overly formal. 
Output ONLY the improved text. No preamble."""

METADATA_PROMPT = """Analyze the following blog post draft. 
Extract a suitable Title and the Date of the event/post if mentioned. 
If no date is mentioned, use today's date ({today}).
Return ONLY a JSON object with keys: "title" (string), "date" (YYYY-MM-DD string).
Text:
"""

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message."""
    await update.message.reply_text(
        "Hi! Send me a rough draft, and I'll help you polish and publish it to your blog."
    )

async def handle_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a user's draft message."""
    original_text = update.message.text
    
    if not GOOGLE_API_KEY:
        await update.message.reply_text("Error: GOOGLE_API_KEY is missing.")
        return

    # 1. Call ID to improve text
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(f"{IMPROVE_PROMPT}\n\n{original_text}")
        improved_text = response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        await update.message.reply_text("Sorry, I couldn't process that with AI right now.")
        return

    # 2. Convert to buttons
    keyboard = [
        [
            InlineKeyboardButton("Do again 🔄", callback_data="action_retry"),
            InlineKeyboardButton("Cancel ❌", callback_data="action_cancel"),
        ],
        [InlineKeyboardButton("Post it ✅", callback_data="action_post")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 3. Send back response (Reply to original so we can track it)
    await update.message.reply_text(
        improved_text,
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    await query.answer() # Acknowledge click

    action = query.data
    improved_message = query.message
    # The original draft is the message the improved_message replied to
    original_message = improved_message.reply_to_message
    
    if action == "action_cancel":
        await improved_message.edit_text("❌ Draft discarded.", reply_markup=None)
        return

    if action == "action_retry":
        if not original_message or not original_message.text:
            await improved_message.display_text("Error: Could not find original draft.", reply_markup=None)
            return
            
        original_text = original_message.text
        
        # Re-run AI
        try:
            model = genai.GenerativeModel('gemini-pro')
            # Add some randomness or temperature? Default is usually deterministic-ish.
            # We can prompt it to be "different"
            response = model.generate_content(f"{IMPROVE_PROMPT} Write it slightly differently this time.\n\n{original_text}")
            new_text = response.text
            
            keyboard = [
                [
                    InlineKeyboardButton("Do again 🔄", callback_data="action_retry"),
                    InlineKeyboardButton("Cancel ❌", callback_data="action_cancel"),
                ],
                [InlineKeyboardButton("Post it ✅", callback_data="action_post")]
            ]
            
            await improved_message.edit_text(new_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"Gemini Retry Error: {e}")
            pass # Keep old text if failed

    if action == "action_post":
        final_text = improved_message.text
        
        await improved_message.edit_text(f"{final_text}\n\n⏳ Publishing...", reply_markup=None)
        
        # 1. Extract Metadata
        try:
            model = genai.GenerativeModel('gemini-pro')
            today_str = datetime.now().strftime('%Y-%m-%d')
            prompt = METADATA_PROMPT.format(today=today_str) + final_text
            
            response = model.generate_content(prompt)
            # Clean response to ensure it's JSON
            json_str = response.text.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3]
            elif json_str.startswith('```'):
                json_str = json_str[3:-3]
                
            metadata = json.loads(json_str)
            title = metadata.get('title', 'Untitled')
            date_str = metadata.get('date', today_str)
            
        except Exception as e:
            logger.error(f"Metadata Error: {e}")
            title = "Untitled Post"
            date_str = datetime.now().strftime('%Y-%m-%d')

        # 2. Construct File Content with Frontmatter
        # We need to match the format expected by generate_posts.py
        # Based on my read, it uses standard Markdown meta, e.g.
        # Title: ...
        # Date: ...
        
        file_content = f"""Title: {title}
Date: {date_str}

{final_text}
"""
        
        # 3. Commit to GitHub
        try:
            if not GITHUB_TOKEN:
                raise ValueError("GITHUB_TOKEN missing")
            
            # Using PyGithub
            # We need to know the repo name. 
            # Since this is running in the repo, we can maybe infer it? 
            # No, we need Environment Variable or hardcode.
            # I'll try to find it from the context or ask user to set GITHUB_REPOSITORY?
            # Creating a file requires the repo object.
            
            # WORKAROUND: For now I will assume the user sets GITHUB_REPOSITORY env var
            # matching "owner/repo".
            repo_name = os.environ.get("GITHUB_REPOSITORY")
            if not repo_name:
                 # Fallback: try to guess or fail
                 raise ValueError("GITHUB_REPOSITORY env var missing. Set it to 'username/repo'.")

            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(repo_name)
            
            # Filename: content/YYYY-MM-DD-slug.md
            slug = title.lower().replace(" ", "-").replace(":", "").replace("/", "")[:50]
            filename = f"content/{date_str}-{slug}.md"
            
            repo.create_file(
                path=filename,
                message=f"New post via Bot: {title}",
                content=file_content,
                branch="main" # or master? I'll assume main.
            )
            
            await improved_message.edit_text(
                f"{final_text}\n\n✅ Published!\nDate: {date_str}\nTitle: {title}\n\n(Rebuild triggered)"
            )
            
        except Exception as e:
            logger.error(f"GitHub Error: {e}")
            await improved_message.edit_text(f"{final_text}\n\n❌ Publish failed: {e}")


# --- Netlify Handler ---

async def main(event):
    """Async main function to handle update."""
    if not TELEGRAM_BOT_TOKEN:
        return {"statusCode": 500, "body": "Bot token missing"}

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft))

    await application.initialize()

    # Parse update
    try:
        data = json.loads(event['body'])
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Process Error: {e}")
        return {"statusCode": 500, "body": str(e)}

    return {"statusCode": 200, "body": "OK"}

def handler(event, context):
    """Entry point for Netlify Function."""
    print("DEBUG: Handler invoked") 
    print(f"DEBUG: Event Body: {event.get('body', 'No Body')}")
    
    # Check dependencies
    if not deps_ok:
        print("CRITICAL: Dependencies missing. Returning 200 to stop retry loop but bot is dead.")
        return {"statusCode": 200, "body": "Dependencies missing"}

    # Check Method
    if event['httpMethod'] != 'POST':
         return {"statusCode": 405, "body": "Method Not Allowed"}
         
    try:
        return asyncio.run(main(event))
    except Exception as e:
        logger.error(f"Top Level Handler Error: {e}")
        traceback.print_exc()
        return {"statusCode": 500, "body": f"Handler Error: {e}"}
