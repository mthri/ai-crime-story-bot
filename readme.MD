# Interactive Detective Story Bot for Telegram

## Overview
This is an AI-powered interactive detective story bot for Telegram that creates personalized crime narratives with branching storylines. The bot leverages large language models (LLMs) to generate unique detective stories in **Persian language** where users make choices that influence how their investigation unfolds.

Each story section presents three options, allowing users to direct the narrative and create a personalized detective experience. The bot can start with pre-generated scenarios or user-created beginnings, making every investigation unique.

## Key Features
- AI-powered interactive storytelling using LLMs
- Branching narratives with user decision points
- Custom or pre-generated story beginnings
- Story rating system
- Optional story cover image generation
- Support for **Telegram** and **Bale** messenger platforms
- Donation and advertisement systems

## Technical Implementation
The bot is built with Python and integrates with OpenAI's language models to generate dynamic story content. It uses a database (PostgreSQL or SQLite) to track user progress and story branches, ensuring consistent narrative experiences across sessions.

## Setup & Configuration

### Prerequisites
- Python 3.9+
- PostgreSQL (optional, SQLite can be used instead)
- Bot Token (obtained from BotFather)
- OpenAI API Key

### Environment Variables
Create a `.env` file in the project root with the following variables:

```env
# OpenAI Configuration
OPENAPI_API_KEY=your_openai_api_key
OPENAPI_URL=https://api.openai.com/v1
OPENAPI_MODEL=gpt-4o-mini
OPENAPI_SECONDARY_MODEL=gpt-4o
INPUT_TOKEN_PRICE=0.001
OUTPUT_TOKEN_PRICE=0.002
MAX_RETRIES=30

# Image Generation (Optional)
STORY_COVER_GENERATION=False
IMAGE_MODEL=dall-e-3
IMAGE_SIZE=1024x1024
IMAGE_PRICE=0.04
IMAGE_DIR=images

# Bot Configuration
BOT_TOKEN=your_telegram_bot_token
SPONSOR_TEXT=Your Sponsor Text
SPONSOR_URL=https://example.com
DONATE_URL=https://example.com/donate
IN_APP_DONATE=False

# Admin Configuration
ADMINS=111111,222222
ADMIN_USERNAME=@your_username
LOG_CHANNEL_ID=12345678

# Wallet Configuration (for donations)
WALLET_TOKEN=your_payment_token

# Feature Flags
MAINTENANCE_MODE=False
MAX_DAILY_STORY_CREATION=2

# Database Configuration
USE_SQLITE=True
# If USE_SQLITE is False, configure PostgreSQL:
PGDB_USER=postgres_user
PGDB_PASS=postgres_password
PGDB_NAME=database_name
PGDB_HOST=localhost
PGDB_PORT=5432

# Messenger Platform
USE_BALE_MESSENGER=False  # Set to True to use Bale messenger instead of Telegram
BOT_CHANNEL=https://t.me/your_channel

# Error Handling
ERROR_MESSAGE_LINK=https://t.me/your_error_channel

# AI Chat feature flag
# Set to False to disable AI chat feature
AI_CHAT=True
```

### Database Setup
The application supports both SQLite and PostgreSQL:

#### Using SQLite (simpler option)
Set `USE_SQLITE=True` in your `.env` file. The database file will be created automatically.

#### Using PostgreSQL
1. Install PostgreSQL if not already installed
2. Create a new database for the project
3. Set the PostgreSQL configuration variables in the `.env` file
4. Set `USE_SQLITE=False`

#### Creating Database Tables
After configuring your database choice, run:
```bash
python models.py
```
This will create all the necessary database tables before running the bot.

### Installing Dependencies
```bash
pip install -r requirements.txt
```

Note: You will need to create a `requirements.txt` file with the following packages:
- python-telegram-bot
- openai
- python-decouple
- psycopg2-binary
- peewee

### Running the Bot
Start the bot with:
```bash
python app.py
```

## Bot Commands
- `/start` - Introduction to the bot and how it works
- `/help` - Show help information about available commands
- `/new` - Start a new story (with or without user-provided scenario)
- `/status` - Show user stats and bot version
- `/support` - Display support options
- `/donate` - Support the bot financially
- `/ads` - Information about advertising opportunities

## Platform Support
The bot can run on either Telegram or Bale messenger platforms:
- To use Telegram (default), set `USE_BALE_MESSENGER=False` in your `.env` file
- To use Bale messenger, set `USE_BALE_MESSENGER=True` which will use the Bale API endpoints instead

## Project Structure
- `app.py` - Main bot application with command handlers and core logic
- `config.py` - Configuration management using environment variables
- `prompts.py` - AI prompts for story generation
- `models.py` - Database models (run this file to create database tables)
- `services.py` - Business logic services
- `utils.py` - Utility functions
- `exceptions.py` - Custom exceptions

## License
This project is licensed under the GNU General Public License v3.0 (GPL-3.0)
