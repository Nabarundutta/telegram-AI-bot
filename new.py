from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from pymongo import MongoClient
import os

# MongoDB Atlas Connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]


# Start command handler
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    first_name = update.message.chat.first_name
    username = update.message.chat.username or "Not Provided"

    # Check if user already exists
    if users_collection.find_one({"chat_id": chat_id}) is None:
        users_collection.insert_one({
            "chat_id": chat_id,
            "first_name": first_name,
            "username": username,
            "phone_number": None
        })

    # Request phone number
    contact_button = KeyboardButton("Share Contact", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True, resize_keyboard=True)

    update.message.reply_text("Please share your phone number to complete registration.", reply_markup=reply_markup)


# Handle contact sharing
def contact_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    phone_number = update.message.contact.phone_number

    users_collection.update_one({"chat_id": chat_id}, {"$set": {"phone_number": phone_number}})
    update.message.reply_text("Thank you! Your registration is complete.")


# Main function
def main():
    application = Application.builder().token(os.getenv("TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
