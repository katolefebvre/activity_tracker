# activity_tracker.py

import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import timezone
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

utc = timezone('UTC')
tz = timezone('America/Toronto')

# Store Activity Check dates
start_date = datetime(2024,6,5)
end_date = datetime(2024,8,5)

async def get_notion_pages(arg: str) -> List[dict]:
    global last_checked
    try:
        pages = notion.databases.query(
            **{
                "database_id": DATABASE_ID,
                "filter": {
                    "and": [ { "property": "owner", "select": { "equals": arg } }, ]
                },
                "sorts": [ { "property": "Name", "direction": "ascending" } ]
            } 
        ).get("results")
        last_checked = datetime.now(tz)
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
    if not args:
        args = ['kato', 'eren', 'dust', 'katie']
    
    for arg in args:
        try:
            response = discord.Embed(
                title       = f"{arg.upper()} - {start_date.strftime("%b").upper()} {start_date.strftime("%d")} TO {end_date.strftime("%b").upper()} {end_date.strftime("%d")}",
                description = '',
                color       = discord.Color.blue()
            )

            pages = await get_notion_pages(arg.lower())
            for page in pages:
                message = format_page_message(page)
                response.add_field(
                    name    = '', 
                    value   = message, 
                    inline  = False)
            try:
                await text.send(embed = response)
            except Exception as e:
                logger.error(f"Error sending message to Discord: {e}")
        except Exception as e:
            logger.error(f"Error polling Notion database: {e}")

@bot.command(name="add")
async def add_activity(text, name, character):
    activity_date = datetime.now(tz)
    activity_date_str = f"{activity_date.strftime('%Y')}-{activity_date.strftime('%m')}-{activity_date.strftime('%d')}"
    
    response = discord.Embed(
        title       = f"{name.upper()}",
        description = '',
        color       = discord.Color.green()
    )
    
    count = 0

    try:
        pages = await get_notion_pages(name.lower())
        for page in pages:
            if page["properties"]["Name"]["title"][0]["text"]["content"].lower() == character.lower():
                if page["properties"]["completed"]["formula"]["string"] == "COMPLETE":
                    response.add_field(
                        name    = 'ACTIVITY COMPLETE', 
                        value   = f'Activity for **{character.upper()}** has already been completed.', 
                        inline  = False)
                    break
                for x in range(1, 11):
                    count += 1
                    
                    if page["properties"][f"day {x}"]["date"] is None:
                        properties = { f"day {x}": { "date": { "start": activity_date_str } } }
                        notion.pages.update(page_id=page["id"], properties=properties)
                        
                        response.add_field(
                            name    = 'ACTIVITY ADDED', 
                            value   = f'Activity for **{character.upper()}** has been created.', 
                            inline  = False)
                        
                        if count == 10:
                            response.add_field(
                                name    = 'ACTIVITY COMPLETE', 
                                value   = f'Congratulations! Activity for **{character.upper()}** has been completed for this check.', 
                                inline  = False)
                        else:
                            response.add_field(
                                name    = '', 
                                value   = f'Current Progress: {count} / 10', 
                                inline  = False)

                        logger.info(f"Activity for {character.upper()} created")

                        break
                    elif page["properties"][f"day {x}"]["date"]["start"] == activity_date_str:
                        response.color = discord.Color.red()
                        response.add_field(
                            name    = 'ACTIVITY ALREADY UPDATED', 
                            value   = f'Activity for **{character.upper()}** has already been updated for today.', 
                            inline  = False)
                        break
    except Exception as e:
        response.color = discord.Color.red()
        response.add_field(
            name    = 'ERROR', 
            value   = f"Error adding activity: {e}", 
            inline  = False)
        logger.error(f"Error adding activity: {e}")
        
    await text.send(embed = response)
    
@bot.command(name="edit")
async def edit_character(text, name, old_chara, new_chara):
    response = discord.Embed(
        title       = f"{old_chara.upper()}",
        description = '',
        color       = discord.Color.green()
    )

    try:
        pages = await get_notion_pages(name.lower())
        for page in pages:
            if page["properties"]["Name"]["title"][0]["text"]["content"].lower() == old_chara.lower():
                properties = { "Name": { "title": [ { "text": { "content": new_chara.lower() } } ] } }
                notion.pages.update(page_id=page["id"], properties=properties)
                
                response.add_field(
                    name    = 'CHARACTER UPDATED', 
                    value   = f'Character name {old_chara.upper()} has been updated to {new_chara.upper()}.', 
                    inline  = False)

                logger.info(f"{character.upper()} updated")
    except Exception as e:
        response.color = discord.Color.red()
        response.add_field(
            name    = 'ERROR', 
            value   = f"Error editing character: {e}", 
            inline  = False)
        logger.error(f"Error editing character: {e}")
        
    await text.send(embed = response)
    
@bot.command(name="new")
async def new_character(text, name, character, vocatum):
    response = discord.Embed(
        title       = f"{name.upper()}",
        description = '',
        color       = discord.Color.green()
    )
    
    try:
        notion.pages.create(
            **{
            "parent": {
                "database_id": DATABASE_ID,
            },
            "properties": {
                "Name": { 
                    "title": [ { 
                        "text": { 
                            "content": character.lower() 
                        } 
                    } ] 
                },
                "owner": {
                    "type": "select",
                    "select": {
                        "name": name.lower()
                    }
                },
                "vocatum": {
                    "type": "select",
                    "select": {
                        "name": vocatum.lower()
                    }
                }
            }
        })
        
        response.add_field(
            name    = 'CHARACTER CREATED', 
            value   = f'Character {character.upper()} has been created for {name.upper()}.', 
            inline  = False)

        logger.info(f"{character.upper()} created")
    except Exception as e:
        response.color = discord.Color.red()
        response.add_field(
            name    = 'ERROR', 
            value   = f"Error creating new character: {e}", 
            inline  = False)
        logger.error(f"Error creating new character: {e}")
    
    await text.send(embed = response)

@bot.command(name="drop")
async def drop_character(text, name, character):
    response = discord.Embed(
        title       = f"{name.upper()}",
        description = '',
        color       = discord.Color.blue()
    )

    try:
        pages = await get_notion_pages(name.lower())
        for page in pages:
            if page["properties"]["Name"]["title"][0]["text"]["content"].lower() == character.lower():
                notion.blocks.delete(block_id=page["id"])
                
                response.add_field(
                    name    = 'CHARACTER DROPPED', 
                    value   = f'Character name {character.upper()} has been dropped.', 
                    inline  = False)

                logger.info(f"{character.upper()} dropped")
    except Exception as e:
        response.color = discord.Color.red()
        response.add_field(
            name    = 'ERROR', 
            value   = f"Error dropping character: {e}", 
            inline  = False)
        logger.error(f"Error dropping character: {e}")
        
    await text.send(embed = response)

@bot.command(name="clear")
async def clear_activity(text, *args):
    if not args:
        args = ['kato', 'eren', 'dust', 'katie']
        
    for arg in args:
        try:
            pages = await get_notion_pages(arg.lower())
            for page in pages:
                try:
                    properties = {
                        "day 1": { "date": None },
                        "day 2": { "date": None },
                        "day 3": { "date": None },
                        "day 4": { "date": None },
                        "day 5": { "date": None },
                        "day 6": { "date": None },
                        "day 7": { "date": None },
                        "day 8": { "date": None },
                        "day 9": { "date": None },
                        "day 10": { "date": None },
                    }
                    notion.pages.update(page_id=page["id"], properties=properties)
                    logger.info("Activity cleared")
                except Exception as e:
                    logger.error(f"Error clearing activity: {e}")
        except Exception as e:
            logger.error(f"Error polling Notion database: {e}")
        
    await text.send("Activity has been cleared.")
    
@bot.command(name="link")
async def post_link(text):
    await text.send("**NOTION LINK:** https://barley-bear.notion.site/2250c04bcbee4f1bbfb48de2ab02e7c7?v=455023601c2947088eed1730da68b834")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)