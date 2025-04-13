import enum
import logging
from logging.handlers import RotatingFileHandler
import traceback
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)

from config import (
    BOT_TOKEN,
    SPONSOR_TEXT,
    SPONSOR_URL,
    ADMINS_ID,
    LOG_CHANNEL_ID,
    STORY_COVER_GENERATION,
    ADMIN_USERNAME,
    WALLET_TOKEN,
    MAX_DAILY_STORY_CREATION,
    DONATE_URL,
    BASE_URL,
    MAINTENANCE_MODE,
    BOT_CHANNEL,
    ERROR_MESSAGE_LINK,
    AI_CHAT,
    IN_APP_DONATE
)
from services import UserService, StoryService, AIStoryResponse, ChatService, user_unlock, asession_lock
from models import User, Story, Section, StoryScenario
from utils import replace_english_numbers_with_farsi, ChatCommand
from exceptions import DailyStoryLimitExceededException, UserNotActiveException
from core import get_account_credit

VERSION = '0.3.0-alpha'

# Configure logging with more detailed format and file rotation
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
file_handler = RotatingFileHandler('bot.log', maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger('app')

# Initialize services
user_service = UserService()
story_service = StoryService()
chat_service = ChatService()

# Message templates for story formatting
STORY_TEXT_FORMAT = '''*{title}*

{body}

*گزینه‌ها:*
{options}
'''

END_STORY_TEXT_FORMAT = '''*{title}*

{body}

'''

# Create sponsor button
sponsor_button = InlineKeyboardButton(SPONSOR_TEXT, url=SPONSOR_URL)

# Keep track of answered messages to prevent duplicates
answered_messages = set()

class ButtonType(enum.Enum):
    """Enum to define types of button interactions."""
    OPTION = 'OPTION'  # For story option selection
    AI_SCENARIOS = 'AI_SCENARIOS'  # For selecting AI-generated scenarios
    STORY_RATE = 'STORY_RATE'
    START = 'START'
    DONATE = 'DONATE'
    ADS = 'ADS'
    DONATE_AMOUNT = 'DONATE_AMOUNT'
    REPORT_AI_CHAT_MSG = 'REPORT_AI_CHAT_MSG'

# New story button
start_new_story_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton('شروع داستان جدید', callback_data=f'{ButtonType.START.value}:None')],
    [InlineKeyboardButton('عضویت در کانال', url=BOT_CHANNEL)]
])

# --- user commands ---

def generate_story_rate_button(story: Story) -> InlineKeyboardMarkup:
    keyboard = []
    option_buttons = []
    
    for index in range(1, 6):
        option_buttons.append(InlineKeyboardButton(
            f'{replace_english_numbers_with_farsi(index)}',
            callback_data=f'{ButtonType.STORY_RATE.value}:{story.id}:{index}'
        ))
    
    keyboard.append(option_buttons)
    # keyboard.append([sponsor_button])
    
    return InlineKeyboardMarkup(keyboard)


def generate_choice_button(section: Section, ai_response: AIStoryResponse) -> InlineKeyboardMarkup:
    """
    Generate inline keyboard buttons for story options.
    
    Args:
        section: The current story section
        ai_response: The AI-generated story response with options
        
    Returns:
        InlineKeyboardMarkup with numbered options and sponsor button
    """
    keyboard = []
    option_buttons = []
    
    for option in ai_response.options:
        option_buttons.append(InlineKeyboardButton(
            f'{replace_english_numbers_with_farsi(option.id)}',
            callback_data=f'{ButtonType.OPTION.value}:{section.id}:{option.id}'
        ))
    
    keyboard.append(option_buttons)
    keyboard.append([sponsor_button])
    
    return InlineKeyboardMarkup(keyboard)


async def send_story_section(update: Update, context: ContextTypes.DEFAULT_TYPE,
                             section: Section, choice: int, user: User) -> None:
    """
    Send the next section of a story based on user's choice.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        section: Current story section
        choice: Option number chosen by the user
    """
    chat_id = update.effective_chat.id
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=chat_id,
        action='typing'
    )
    previous_section = section
    
    # Generate next section based on choice
    section, ai_response = await story_service.create_section(user, section.story, choice)
    #TODO if error delete section 
    # Mark previous section as used to prevent re-use
    story_service.mark_section_as_used(previous_section)
    
    # Prepare message text and options based on whether story has ended
    if not ai_response.is_end:
        reply_markup = generate_choice_button(section, ai_response)
        text = STORY_TEXT_FORMAT.format(
            title=ai_response.title,
            body=ai_response.story,
            options='\n'.join([f'{option.id}- {option.text}' for option in ai_response.options])
        )
    else:
        reply_markup = generate_story_rate_button(section.story)
        text = END_STORY_TEXT_FORMAT.format(
            title=ai_response.title,
            body=ai_response.story,
            options='\n'.join([f'{option.id}- {option.text}' for option in ai_response.options])
        )
        text += '** نظرت درباره این داستان چی‌بود؟ 😃 از ۱ (خیلی بد) تا ۵ (عالی) بهم یه نمره بده! ⭐📖**'

    # Send the message with story text
    await context.bot.send_message(
        chat_id=chat_id,
        text=replace_english_numbers_with_farsi(text),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f'Sent story section to user {update.effective_user.id}')


async def send_ai_generated_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a list of AI-generated story scenarios for the user to choose from.
    
    Args:
        update: Telegram update object
    """
    # Get unused AI scenarios
    scenarios = await story_service.get_unused_scenarios()
    keyboard = []
    text = '*یک داستان رو انتخاب کن:*\n\n' 
    
    # Generate buttons and formatted text for each scenario
    scenario_buttons = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_buttons.append(InlineKeyboardButton(
            f'{replace_english_numbers_with_farsi(index)}',
            callback_data=f'{ButtonType.AI_SCENARIOS.value}:{scenario.id}'
        ))
        text += f'*{index}*- {scenario.text}\n\n'
    
    keyboard.append(scenario_buttons)
    keyboard.append([sponsor_button])
    
    # Send the message with scenarios
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(text),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    logger.info(f'Sent AI scenarios to user {update.effective_user.id}')


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command to introduce the bot to new users.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    text = '''سلام! 👋
من یک کارآگاه هوش مصنوعی هستم که با جدیدترین مدل‌های زبانی، داستان‌های جنایی منحصربه‌فردی برای تو می‌سازم! 🔎

🔹 هر داستان مخصوص تو خلق می‌شه، هیچ‌کس دیگه‌ای تجربه‌ی مشابهی نخواهد داشت!
🔹 در هر مرحله، انتخاب‌هایی داری که مسیر داستان رو تغییر می‌ده. اما مراقب باش، این انتخاب‌ها برگشت‌ناپذیرن! 🤯
🔹 برای شروع، دستور /new رو بفرست یا هر سناریویی دوست داری، فقط متنشو بفرست 😊
🔹 برای راهنما، دستور /help رو امتحان کن.
🔹 برای حمایت از ما، دستور /support رو بفرست.

*آها راستی! با این ربات می‌تونی گپ بزنی 😀*

🎭 آماده‌ای وارد دنیای رازآلود من بشی؟ یه معمای جذاب در انتظارت هست! 🕵️‍♂️'''

    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(text),
        reply_markup=start_new_story_keyboard,
        parse_mode='Markdown'
    )
    logger.info(f'New user started the bot: {update.effective_user.id}')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command to display usage instructions.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    text = f'''📌 *راهنمای ربات من*  

👋 سلام! اینجا می‌تونی داستان‌های جنایی منحصر‌به‌فرد خودت رو بسازی. برای استفاده از ربات، این دستورات رو در نظر داشته باش:  

🔹 /new – شروع یک داستان جدید  
- اگر این دستور رو *بدون متن* بفرستی، هوش مصنوعی چند سناریو جذاب پیشنهاد می‌کنه و تو می‌تونی یکی رو انتخاب کنی.  

🔹 می‌خوای تو شروع‌کننده‌ی داستان باشی؟ پس فقط سناریوتو بفرست! 😄
 

📢 *نکته:* این ربات در حال توسعه هست! اگر مشکلی دیدی یا پیشنهادی داشتی، از طریق [این آیدی]({ADMIN_USERNAME}) با ما در ارتباط باش.  

🔍 آماده‌ای رازها رو کشف کنی؟ فقط یه دستور کافیه! 🚀  
'''
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(text),
        reply_markup=start_new_story_keyboard,
        parse_mode='Markdown'
    )
    logger.info(f'Help command used by user {update.effective_user.id}')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = user_service.get_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name,
        update.effective_user.last_name
    )
    stories_count, section_count, charge = await story_service.damage_report(user)
    charge = round(abs(charge), 4)
    text = f'''ممنون که تا اینجا باهام بودی! 😊
تا الان با هم {stories_count} تا داستان ساختیم، {section_count} تا تصمیم گرفتیم و خب... {charge} دلار هم خرج رو دستم گذاشتی! ولی فدای سرت! 💸
پولش رو از هر جایی که شد جور کردیم، از سرمایه‌گذار بگیر تا تبلیغات! 😅
مهم اینه که تو باهاش حال کرده باشی! 🎉

ver: {VERSION}'''
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(text),
        parse_mode='Markdown'
    )
    logger.info(f'Status command used by user {update.effective_user.id}')


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f'Donate command used by user {update.effective_user.id}')
    if not IN_APP_DONATE:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'برای حمایت مالی از ما می‌تونید از طریق لینک زیر اقدام کنید 😊\n\n{DONATE_URL}' 
        )
        return None
    keyboard = [
        [InlineKeyboardButton('۵ هزار تومان (برنز)', callback_data=f'{ButtonType.DONATE_AMOUNT.value}:50000')],
        [InlineKeyboardButton('۱۰ هزار تومان (نقره‌ای)', callback_data=f'{ButtonType.DONATE_AMOUNT.value}:10000')],
        [InlineKeyboardButton('۵۰ هزار تومان (طلایی)', callback_data=f'{ButtonType.DONATE_AMOUNT.value}:500000')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = '''💙 *حمایت از ما = حمایت از خیریه‌ها!*

ما متعهد شدیم خدماتمون رایگان باشه، اما برای ادامه کار به حمایت شما نیاز داریم. 
با دونیت شما، نه‌تنها به پایداری این پروژه کمک می‌کنید، بلکه در صورت تأمین هزینه‌ها، تبلیغات خیریه‌ها رو *رایگان* انجام خواهیم داد. 🎗️
✅ هر مبلغی که مایلید انتخاب کنید و همراه ما باشید:
    '''

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f'Ads command used by user {update.effective_user.id}')
    text = f'''📢 *تبلیغ کسب‌وکار شما در بهترین جای ممکن!*

ما زیر هر داستان یک دکمه اختصاصی قرار دادیم که محل تبلیغ شماست! 🚀  
کاربران با کلیک روی این دکمه، مستقیماً به لینک موردنظر شما هدایت می‌شوند. این یعنی تبلیغ شما در معرض دید هزاران نفر قرار می‌گیرد!  

🎯 *اگر می‌خواهید کسب‌وکارتان دیده شود، همین حالا اقدام کنید!*
برای سفارش تبلیغ، با [این آیدی]({ADMIN_USERNAME}) در ارتباط باشید.

'''
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode='Markdown'
    )
    logger.info(f'Ads command used by user {update.effective_user.id}')


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f'Support command used by user {update.effective_user.id}')
    keyboard = [
        [InlineKeyboardButton('📢 سفارش تبلیغ', callback_data=f'{ButtonType.ADS.value}')],
        [InlineKeyboardButton('❤️ حمایت مالی (دونیت)', callback_data=f'{ButtonType.DONATE.value}')],
        [InlineKeyboardButton('☕ باهم یک قهوه بزنیم؟ (دونیت)', url=DONATE_URL)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = '''🎯 ما متعهد شدیم که خدماتمون رایگان باشه، اما برای ادامه کار به حمایت شما نیاز داریم.

✅ *دو راه برای حمایت از ما:*

1️⃣ *سفارش تبلیغ* – تبلیغ کسب‌وکار یا محصولتون رو با ما انجام بدید.
2️⃣ *حمایت مالی (دونیت)* – اگر هزینه‌ها با دونیت تأمین بشه، تبلیغات خیریه‌ها رو رایگان انجام می‌دیم. یعنی شما هم به خیریه‌ها کمک کردید! 💙

🙏 با حمایت شما، می‌تونیم این مسیر رو ادامه بدیم!'''
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def new_story_command(update: Update,  context: ContextTypes.DEFAULT_TYPE,
                            user: User | None = None, scenario_text: str | None = None, 
                            scenario_obj: StoryScenario | None = None) -> None:
    """
    Start a new story based on user input or AI-generated scenario.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        scenario_text: Custom scenario text from user (optional)
        scenario_obj: Pre-generated scenario object (optional)
    """
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    
    if not user:
        user = user_service.get_user(
            update.effective_user.id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name
        )
    
    await chat_service.deactivate_current_session(user)
    
    # If no scenario is provided, show AI-generated options
    if not scenario_text and not scenario_obj:
        await send_ai_generated_scenario(update, context)
        return None
    
    # Deactivate any active stories for this user
    await story_service.deactivate_active_stories(user)
    
    # Create a new story
    story = await story_service.create(user)
    
    # Set up the scenario
    if scenario_text:
        scenario = story_service.create_scenario(
            story,
            text=scenario_text
        )
    elif scenario_obj:
        scenario = scenario_obj
    else:
        logger.error(f'Invalid scenario for user {update.effective_user.id}')
        raise ValueError('Invalid scenario: both scenario_text and scenario_obj are None')
    
    # Delete the AI scenarios list message if possible
    try:
        await update.effective_message.delete()
    except Exception as e:
        logger.warning(f'Could not delete message: {e}')
    
    # Send the scenario text
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(scenario.text),
        parse_mode='Markdown'
    )
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    
    # Start the story with the chosen scenario
    section, ai_response = await story_service.start_story(story, scenario, user)
    
    # Prepare reply markup with options
    reply_markup = generate_choice_button(section, ai_response)
    
    # Format the story text
    text = STORY_TEXT_FORMAT.format(
        title=ai_response.title,
        body=ai_response.story,
        options='\n'.join([f'*{option.id}-* {option.text}' for option in ai_response.options])
    )

    # Send the first story section
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=replace_english_numbers_with_farsi(text),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f'New story started for user {update.effective_user.id}')


# --- admin commands ---

async def admin_charge_command(update: Update, context: ContextTypes.DEFAULT_TYPE, *args) -> None:
    credit = await get_account_credit()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Account credit: {credit}'
    )


async def admin_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE, *args) -> None:
    raise NotImplementedError


async def admin_user_action_command(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, action: str, *args) -> None:
    if user_id.isnumeric():
        user = user_service.get_user(int(user_id))
    else:
        user = user_service.get_by_username(user_id)
    
    if action == 'chrge':
        amount = int(args[0])
        user.charge += amount
        user.save()
    elif action == 'ban':
        user.active = False
        user.save()
    elif action == 'unban':
        user.active = True
        user.save()
    elif action == 'info':
        report = await story_service.damage_report(user)
        text = f'''ID: {user.user_id}
Username: {user.username}
First name: {user.first_name}
Last name: {user.last_name}
Active: {user.active}
Charge: {user.charge}
Joined at: {user.created_at}
Story Count: {report[0]}
Section Count: {report[1]}'''
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text
        )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Done!'
    )


# Command handler mapping
commands = {
    '/start': start_command,
    '/help': help_command,
    '/new': new_story_command,
    '/status': status_command,
    '/support': support_command,
    '/donate': donate_command,
    '/ads': ads_command,
    '!chrg': admin_charge_command,
    '!rprt': admin_report_command,
    '!usr': admin_user_action_command
}


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User) -> None:
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    response = await chat_service.chat(user, update.message.text)
    if response.COMMAND == ChatCommand.CHAT_TEXT:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response.TEXT,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('گزارش این پیام', callback_data=f'{ButtonType.REPORT_AI_CHAT_MSG.value}')]])
        )
    elif response.COMMAND == ChatCommand.SEND_AI_SCENARIO:
        await send_ai_generated_scenario(update, context)
    elif response.COMMAND == ChatCommand.USER_SCENARIO:
        await new_story_command(update, context, user, scenario_text=response.TEXT)
    elif response.COMMAND == ChatCommand.END_STORY:
        await new_story_command(update, context, user)


async def donate_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> None:
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title='🌟 حمایت از ما = حمایت از خیریه‌ها!',
        description=(
            'با حمایت مالی شما، این پروژه به فعالیت خودش ادامه می‌ده و در صورت تأمین هزینه‌ها، '
            'ما تبلیغات خیریه‌ها رو به‌صورت رایگان انجام می‌دیم. یعنی شما هم در این کار خیر سهیم هستید! 💙'
        ),
        payload=uuid.uuid4().hex,
        provider_token=WALLET_TOKEN,
        prices=[
            LabeledPrice(label='💰 مبلغ حمایت', amount=amount),
        ],
        currency='IRR',
    )
    logger.info(f'Invoice sent for user {update.effective_user.id} with amount {amount}')


@asession_lock
async def new_message(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      user: User | None = None) -> None:
    """
    Handle new messages from users.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    # Ignore messages from groups or channels, only process private messages
    if not update.message or update.message.chat.type != 'private':
        logger.info(f'Ignored non-private message')
        return None
    
    # Prevent duplicate processing of messages
    if update.message.id in answered_messages:
        logger.debug(f'Ignored duplicate message {update.message.id}')
        return None
    
    answered_messages.add(update.message.id)

    if not user:
        user = user_service.get_user(
            update.effective_user.id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name
        )
    
    # Log the incoming message
    logger.info(f'Received message from {update.effective_user.id}: {update.message.text[:20]}...')
    
    # Handle commands
    if update.message.text.startswith('/'):
        command = update.message.text.split()[0]
        if command == '/new':
            # Extract scenario text after "/new"
            scenario_text = update.message.text[4:].strip()
            await new_story_command(update, context, user, scenario_text=scenario_text)
            return None
        elif command in commands:
            await commands[command](update, context)
            return None
    
    # Handle Admin commands
    if update.message.text.startswith('!') and user.user_id in ADMINS_ID:
        command, *args = update.message.text.split()
        if command in commands:
            return await commands[command](update, context, *args)

    if AI_CHAT:
        await chat(update, context, user)
    else:
        # Default response for unrecognized messages
        await update.message.reply_text(
            'متوجه منظورت نشدم 🤔\nبهتر از دستور /help استفاده کنی.',
            parse_mode='Markdown'
        )
        logger.info(f'Sent help suggestion to user {update.effective_user.id}')


@asession_lock
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       user: User | None = None) -> None:
    """
    Handle inline button clicks from users.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    # Prevent duplicate processing
    if update.update_id in answered_messages:
        logger.debug(f'Ignored duplicate button click {update.update_id}')
        return None
    
    answered_messages.add(update.update_id)
    
    if not user:
        # Get user information
        user = user_service.get_user(
            update.effective_user.id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name
        )
    
    # Process button data
    query = update.callback_query
    query_data = query.data
    
    # Answer the callback query to stop "loading" animation
    # await query.answer()
    
    # Parse button data
    btype, *data = query_data.split(':')
    logger.info(f'Button click: {btype} from user {update.effective_user.id}')
    
    if btype == ButtonType.OPTION.value:
        # Handle story option selection
        section_id = int(data[0])
        option = int(data[1])
        
        # Get unused section (prevents users from using old sections)
        section = await story_service.get_unused_section(section_id)
            
        if not section:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="نمی‌تونی به عقب برگردی... انتخابت رو کردی! 😉🔥",
                parse_mode="Markdown"
            )
            logger.warning(f'User {update.effective_user.id} tried to use an already used section')
            return None
            
        # Send next story section based on choice
        await send_story_section(update, context, section, option, user)
            
    elif btype == ButtonType.AI_SCENARIOS.value:
        # Handle AI scenario selection
        scenario_id = int(data[0])
        scenario = story_service.get_scenario(scenario_id)
        await new_story_command(update, context, user, scenario_obj=scenario)

    elif btype == ButtonType.STORY_RATE.value:
        story_id = int(data[0])
        story = await story_service.get_by_id(story_id)
        if story.rate == None:
            await story_service.update_story_rate(story, int(data[1]))
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                reply_markup=start_new_story_keyboard,
                text='نظرت ثبت شد! ممنون که وقت گذاشتی و داستان رو ارزیابی کردی.\nبا کمک بازخوردت سعی می‌کنم بهتر بشم! ⭐✨',
                parse_mode="Markdown"
            )
            if STORY_COVER_GENERATION:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text='یکم صبر کن، دارم برای داستانت کاور درست می‌کنم. 😊',
                )
                image_path = await story_service.generate_story_cover(story, user)
                with open(image_path, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=f,
                        caption='امیداروم از این داستان لذت برده باشی! 🤗'
                    )
            await support_command(update, context)

    elif btype == ButtonType.START.value:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action='typing'
        )
        await send_ai_generated_scenario(update, context)

    elif btype == ButtonType.ADS.value:
        await ads_command(update, context)

    elif btype == ButtonType.DONATE.value:
        await donate_command(update, context)

    elif btype == ButtonType.DONATE_AMOUNT.value:
        amount = int(data[0])
        await donate_payment(update, context, amount=amount)

    else:
        # Unknown button type
        logger.warning(f'Unknown button type: {btype} from user {update.effective_user.id}')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='دنبال چی می‌گردی، شیطون؟ 😏🔍',
            parse_mode='Markdown'
        )


async def daily_limit_exception_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = f'''سلام عزیزم! 👋

ما اینجا هستیم که رایگان برات داستان بسازیم! ✨ ولی هزینه‌ها زیاده! 😅💸 برای ادامه کار، {replace_english_numbers_with_farsi(MAX_DAILY_STORY_CREATION)} داستان در هر ۲۴ ساعت محدودیت داریم. 🤏

اگه دوست داری همیشه با ما باشی، دستور /support رو ارسال کن! ❤️

ممنون که درک می‌کنی! 🙏🔥'''
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors that occur during message processing.
    
    Args:
        update: Telegram update object
        context: Telegram context object with the error
    """
    if update:
        user = user_service.get_user(update.effective_user.id, only_active=False)
        user_unlock(user)
    
    if isinstance(context.error, DailyStoryLimitExceededException):
        await daily_limit_exception_message(update, context)
        return None
    elif isinstance(context.error, UserNotActiveException):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='حساب کاربری شما غیرفعال شده است. با ادمین تماس بگیرید. 🤝'
            )
        except Exception as e:
            logger.exception(e)
        return None
    
    # Format the error traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    error_code = uuid.uuid4().hex
    # Get update info if available
    update_str = update.to_dict() if update else 'No update'
    
    # Log detailed error information
    error_message = f'{error_code} Exception: {context.error}\n\nTraceback:\n{tb_string}\n\nUpdate: {update_str}'
    logger.error(error_message)
    
    # Send friendly error message to user
    try:
        if update and update.effective_chat:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton('چی شد؟', url=ERROR_MESSAGE_LINK)]
            ])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=('اوه نه! یه چیزی این وسط ناجور شد 😅 ولی نگران نباش، دارم بررسیش می‌کنم! 🔍✨ \n'
                      'یه کم صبر کن و چند دقیقه دیگه دوباره امتحان کن 😉\n'
                      'بوس بهت 😘\n\n'
                      f'کد پیگیری: ```{error_code}```'
                    ),
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            logger.info(f'Sent error message to user {update.effective_chat.id}')
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=f' {type(context.error)}\n```{error_code}```',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f'Error sending error message: {e}')


async def on_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='دارم خودمو آپدیت می‌کنم، یه چیزی تو مایه‌های رژیم و باشگاه رفتن برای رباتا! 🤖💪 یه کم صبر کنی، بهتر از قبل برمی‌گردم! 😎'
    )


def main() -> None:
    """
    Main function to run the bot.
    
    Initializes the Telegram bot application, sets up handlers,
    and starts polling for updates.
    """
    logger.info('Starting Mystery Bot...')
    
    # Initialize the application with Bale bot token
    application = Application.builder().token(BOT_TOKEN)\
                             .base_url(BASE_URL)\
                             .build()
    
    if not MAINTENANCE_MODE:
        # Set up command handlers
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('start', start_command))
        application.add_handler(CommandHandler('status', status_command))
        application.add_handler(CommandHandler('support', support_command))
        application.add_handler(CommandHandler('donate', donate_command))
        application.add_handler(CommandHandler('ads', ads_command))
        application.add_handler(CommandHandler('new', new_story_command))
        
        # Set up text message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, new_message))
        
        # Set up button click handler
        application.add_handler(CallbackQueryHandler(button_click))
        
        # Set up error handler
        application.add_error_handler(error_handler)
    else:
        application.add_handler(MessageHandler(filters.TEXT, on_maintenance))
    
    # Start the bot
    logger.info('Bot is running!')
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()