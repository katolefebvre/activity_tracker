# activity_tracker.py

import os
import asyncio
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
from typing import List

import discord
from discord.ext import commands
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve values from environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()

# Configure logging
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
)
logger = logging.getLogger(__name__)
logger.setLevel(LOGLEVEL)
logger.addHandler(console_handler)

# Create default intents and disable members intent
intents = discord.Intents.default()
intents.message_content = True

# Initialize the Discord bot with the specified intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize the Notion client
notion = Client(auth=NOTION_API_KEY)

# Store the last checked timestamp
last_checked = datetime.now().replace(microsecond=0).isoformat()

start_date = datetime(2024,2,5)
end_date = datetime(2024,4,5)

async def get_notion_pages(arg: str) -> List[dict]:
    global last_checked
    try:
        pages = notion.databases.query(
            **{
                "database_id": DATABASE_ID,
                "filter": {
                    "and": [
                        {
                            "property": "owner",
                            "select": {
                                "equals": arg
                            }
                        },
                    ]
                },
                "sorts": [
                    {
                        "property": "Name",
                        "direction": "ascending"
                    }
                ]
            }
        ).get("results")
        last_checked = datetime.utcnow().replace(microsecond=0).isoformat()
        logger.info(f"Last checked at: {last_checked}")
        logger.debug(pages)
        return pages
    except Exception as e:
        logger.error(f"Error fetching pages from Notion: {e}")
        return []


def format_page_message(page: dict) -> str:
    count = 0
    title = page["properties"]["Name"]["title"][0]["text"]["content"].upper()
    emoji = ":red_square:"

    if page["properties"]["completed"]["formula"]["string"] == "COMPLETE":
        count = 10
        emoji = ":green_square:"
    else:
        for x in range(1, 10):
            try:
                if len(page["properties"][f"day {x}"]["date"]["start"]) > 0:
                    count = count + 1
            except Exception as e:
                break
        
    message = f"{emoji} **{title}** - {count} / 10\n"
    return message

@bot.event
async def on_ready() -> None:
    logger.info(f"{bot.user} is now online!")

@bot.event
async def on_message(message):
  await bot.process_commands(message)

@bot.command(name="ac")
async def check_activity(text, *args):
    await text.send(f'# ACTIVITY CHECK - 
                    {start_date.strftime("%b").upper()} {start_date.strftime("%d")} 
                    TO {end_date.strftime("%b").upper()} {end_date.strftime("%d")}')
    
    if not args:
        args = ['kato', 'eren', 'dust', 'katie']
    
    for arg in args:
        try:
            response = discord.Embed(
                title       = f"{arg.upper()}",
                description = '',
                color       = discord.Color.blue()
            )

            pages = await get_notion_pages(arg.lower())
            for page in pages:
                message = format_page_message(page)
                response.add_field(
                    name = '',
                    value = message,
                    inline = False
                )
            try:
                await text.send(embed = response)
            except Exception as e:
                logger.error(f"Error sending message to Discord: {e}")
        except Exception as e:
            logger.error(f"Error polling Notion database: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)