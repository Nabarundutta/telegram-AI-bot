from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackContext, MessageHandler
import pymongo
import google.generativeai as genai
import pytz
from telegram.ext import ApplicationBuilder, filters
from telegram import KeyboardButton, ReplyKeyboardMarkup
import os
from datetime import datetime
from telegram.ext import (
    CommandHandler, MessageHandler, filters, CallbackContext
)
from bs4 import BeautifulSoup
import requests


app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
app.job_queue.scheduler.configure(timezone=pytz.utc)
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client['bot-Database']
user_collection = db['bot-collection']
chat_collection = db['chat_history']
file_collection = db['file_history']
search_collection = db['search_history']
genai.configure(api_key="AIzaSyBl11IZA8jERtojyDUSXbZNWbMS3sXDMk4")
model = genai.GenerativeModel("gemini-1.5-flash")
## starting from here

def perform_web_search(query):
    search_url = f"https://search.brave.com/search?q={query}&source=web"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        search_results = soup.find_all("a", href=True)[:5]
        links = [link["href"] for link in search_results if "http" in link["href"]]

        return links[:5]
    return []


# Handle Web Search
async def web_search(update: Update, context: CallbackContext) -> None:
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Please provide a search query. Example: `/websearch AI trends`")
        return

    # Perform web search
    links = perform_web_search(query)

    # Generate AI Summary
    try:
        response = model.generate_content(f"Summarize the latest web search results for: {query}")
        summary = response.text if response.text else "No summary available."
    except Exception as e:
        summary = "Error generating summary."

    # Store in MongoDB
    search_collection.insert_one({
        "query": query,
        "links": links,
        "summary": summary,
        "user_id": update.message.chat_id
    })

    # Send response
    result_text = f"🔍 **Web Search Results for:** {query}\n\n📌 **Summary:** {summary}\n\n🔗 **Top Links:**\n"
    result_text += "\n".join(links) if links else "No links found."

    await update.message.reply_text(result_text, disable_web_page_preview=True)


async def image_handle(update:Update,context: CallbackContext)-> None:
    chat_id = update.message.chat_id
    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    file_name = file.file_name if hasattr(file, 'file_name') else "image.jpg"
    timestamp = datetime.utcnow()

    # Ensure the 'downloads' directory exists
    os.makedirs("downloads", exist_ok=True)

    # Download the file
    file_obj = await context.bot.get_file(file_id)
    file_path = f"downloads/{file_name}"
    await file_obj.download_to_drive(file_path)

    try:
        # Use Gemini to analyze the file
        response = model.generate_content(f"Describe the content of this file: {file_path}")
        description = response.text if response.text else "No description available."

        # Save file metadata in MongoDB
        file_collection.insert_one({
            "chat_id": chat_id,
            "file_name": file_name,
            "file_id": file_id,
            "description": description,
            "timestamp": timestamp
        })
        await update.message.reply_text(f"📄 **File Analysis:**\n{description}")

    except Exception as e:
        await update.message.reply_text("⚠️ Error processing your file.")
        print(f"Error: {e}")

async def chat(update: Update,context: CallbackContext)-> None:
    await update.message.reply_text("Welcome AI powered chat , How may i help you")

async def message_handler(update:Update,context:CallbackContext)->None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    timestamp = datetime.utcnow()
    try:
        response = model.generate_content(user_text)
        bot_reply = response.text if response.text else "Sorry pls try again"

        chat_collection.insert_one({
            "chat_id": chat_id,
            "user_message": user_text,
            "bot_response": bot_reply,
            "timestamp": timestamp
        })

        await update.message.reply_text(bot_reply)
    except Exception as e:
        await update.message.reply_text("⚠️ Error processing your request.")
        print(f"Error: {e}")


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    first_name = update.message.chat.first_name
    user_name = update.message.chat.username or "Not Provided"

    ## check if the user already present or not
    user = user_collection.find_one({"chat_id": chat_id})
    # if not
    if not user:
        user_collection.insert_one({
            "chat_id": chat_id,
            "first_name": first_name,
            "username": user_name,
            "phone_number": None
        })
    contact_button = KeyboardButton("Share Contact",request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Please share your phone number to complete registration.",
                                    reply_markup=reply_markup)
async def about(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    await update.message.reply_text("/hello -> to print your name")

# Handle contact sharing
async def contact_handler(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    phone_number = update.message.contact.phone_number

    user_collection.update_one({"chat_id": chat_id}, {"$set": {"phone_number": phone_number}})
    await update.message.reply_text("✅ Thank you! Your registration is complete.")

def main():

    app = ApplicationBuilder().token("7427132300:AAEMnp7JrgBoU13-Qzj-hopoV4KcCARJZFQ").build()


    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("about",about))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(CommandHandler("chat",chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, image_handle))

    app.add_handler(CommandHandler("websearch", web_search))

    app.run_polling()

if __name__ == "__main__":
    main()