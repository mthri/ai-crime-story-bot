import enum
import logging
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import BALE_BOT_TOKEN, SPONSOR_TEXT, SPONSOR_URL
from services import UserService, StoryService, AIStoryResponse
from models import User, Story, Section, StoryScenario

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('app')

ADMINS = [
]

user_service = UserService()
story_service = StoryService()

STORY_TEXT_FORMAT = '''*{title}*

{body}

*گزینه‌ها:*
{options}
'''

END_STORY_TEXT_FORMAT = '''*{title}*

{body}
'''


sponsor = InlineKeyboardButton(SPONSOR_TEXT, url=SPONSOR_URL)
answered = set()

class ButtonType(enum.Enum):
    OPTION = 'OPTION'
    AI_SCENARIOS = 'AI_SCENARIOS'


def generate_choice_button(section: Section, ai_response: AIStoryResponse) -> InlineKeyboardMarkup:
    keyboard = []
    for option in ai_response.options:
        keyboard.append(InlineKeyboardButton(
            f'{option.id}',
            callback_data=f'{ButtonType.OPTION.value}:{section.id}:{option.id}'
        ))
    
    return InlineKeyboardMarkup([keyboard, [sponsor]])

async def send_story_section(update: Update, context: ContextTypes.DEFAULT_TYPE,
                             section: Section, choice: int) -> None:
    
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    story_service.mark_section_as_used(section)
    section, ai_response = await story_service.create_section(section.story, choice)

    if not ai_response.is_end:
        reply_markup = generate_choice_button(section, ai_response)
        text = STORY_TEXT_FORMAT.format(
            title=ai_response.title,
            body=ai_response.story,
            options='\n'.join([f'{option.id}- {option.text}' for option in ai_response.options])
        )
    else:
        reply_markup = None
        text = END_STORY_TEXT_FORMAT.format(
            title=ai_response.title,
            body=ai_response.story,
            options='\n'.join([f'{option.id}- {option.text}' for option in ai_response.options])
        )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup
    )

async def send_ai_generated_scenario(update: Update) -> None:
    scenarios = await story_service.get_unused_scenarios()
    keyboard = []
    text = ''
    for index, scenario in enumerate(scenarios, start=1):
        keyboard.append(InlineKeyboardButton(
            f'{index}',
            callback_data=f'{ButtonType.AI_SCENARIOS.value}:{scenario.id}'
        ))
        text += f'*{index}*- {scenario.text}\n\n'
    
    await update.message.reply_text(
       text,
       reply_markup=InlineKeyboardMarkup([keyboard, [sponsor]])
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = '''سلام! 👋
من یک کارآگاه هوش مصنوعی هستم که با جدیدترین مدل‌های زبانی، داستان‌های جنایی منحصربه‌فردی برای تو می‌سازم! 🔎

🔹 هر داستان مخصوص تو خلق می‌شه، هیچ‌کس دیگه‌ای تجربه‌ی مشابهی نخواهد داشت!
🔹 در هر مرحله، انتخاب‌هایی داری که مسیر داستان رو تغییر می‌ده. اما مراقب باش، این انتخاب‌ها برگشت‌ناپذیرن! 🤯
🔹 برای شروع، دستور /new رو بفرست.
🔹 برای راهنما، دستور /help رو امتحان کن.

🎭 آماده‌ای وارد دنیای رازآلود من بشی؟ یه معمای جذاب در انتظارت هست! 🕵️‍♂️'''

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = '''📌 *راهنمای ربات مستر میستری*  

👋 سلام! اینجا می‌تونی داستان‌های جنایی منحصر‌به‌فرد خودت رو بسازی. برای استفاده از ربات، این دستورات رو در نظر داشته باش:  

🔹 */new* – شروع یک داستان جدید  
- اگر این دستور رو *بدون متن* بفرستی، هوش مصنوعی چند سناریو جذاب پیشنهاد می‌کنه و تو می‌تونی یکی رو انتخاب کنی.  
- اگه *بعد از این دستور، سناریوی مدنظرت رو بنویسی*، داستان دقیقاً طبق ایده‌ی تو جلو می‌ره!  

مثال:
``` /new یک کارآگاه خصوصی در یک شب بارانی بسته‌ای ناشناس دریافت می‌کند... ```
🔸 بعد از ارسال این پیام، ربات داستان رو بر اساس سناریوی تو ادامه می‌ده!  

📢 *نکته:* این ربات در حال توسعه هست! اگر مشکلی دیدی یا پیشنهادی داشتی، از طریق آیدی @mthri با ما در ارتباط باش.  

🔍 آماده‌ای رازها رو کشف کنی؟ فقط یه دستور کافیه! 🚀  

'''
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

async def new_story_command(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            scenario_text: str = None, scenario_obj: StoryScenario = None) -> None:
    if not scenario_text and not scenario_obj:
        await send_ai_generated_scenario(update)
        return None
    
    user = user_service.get_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name,
        update.effective_user.last_name
    )
    await story_service.deactivate_active_stories(user)
    story = await story_service.create(user)
    if scenario_text:
        scenario = story_service.create_scenario(
            story,
            text=scenario_text
        )
    elif scenario_obj:
        scenario = scenario_obj
    else:
        raise Exception('Invalid scenario')
    
    # delete list of ai scenarios
    #TODO in ai scenarios messsage, deleted
    await update.effective_message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=scenario.text
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    
    section, ai_response = await story_service.start_story(story, scenario)
    reply_markup = generate_choice_button(section, ai_response)
    text = STORY_TEXT_FORMAT.format(
        title=ai_response.title,
        body=ai_response.story,
        options='\n'.join([f'{option.id}- {option.text}' for option in ai_response.options])
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup
    )


commands = {
    '/start': start_command,
    '/help': help_command,
    '/new': new_story_command,
}


async def new_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ignore messages from groups or channels, only process private messages
    if update.message.chat.type != 'private':
        return None
    
    #TODO remove it later
    if update.message.id in answered:
        return None
    else:
        answered.add(update.message.id)
    
    if update.message.text.startswith('/') and commands.get(update.message.text):
        await commands[update.message.text](update, context)
        return None
    elif update.message.text.startswith('/new'):
        await new_story_command(update, context, scenario_text=update.message.text.strip('/new'))
    
    await update.message.reply_text(
       'متوجه منظورت نشدم 🤔\nبهتر از دستور /help استفاده کنی.'
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """This function will handle the click event of the inline button."""
    #TODO remove later
    if update.update_id in answered:
        return None
    else:
        answered.add(update.update_id)
    
    user = user_service.get_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name,
        update.effective_user.last_name
    )
    query = update.callback_query
    query_data = query.data
    btype, *data = query_data.split(':')
    
    if btype == ButtonType.OPTION.value:
        # for ignore user to use old section response
        section = await story_service.get_unused_section(int(data[0]))
        if not section:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='نمی‌تونی به قبل برگردی، انتخابت رو کردی! :)'
            )
            return None
        option = int(data[1])
        await send_story_section(update, context, section, option)
    
    elif btype == ButtonType.AI_SCENARIOS.value:
        scenario_id = int(data[0])
        scenario = story_service.get_scenario(scenario_id)
        await new_story_command(update, context, scenario_obj=scenario)
    
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="دنبال چی می‌گردی، شیطون؟ 😏🔍"
        )

async def error_handler(update, context):
    """Log the error and send a message to the user."""
    # Log the error
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Gather error information
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)    
    update_str = update.to_dict() if update else 'No update'
    message = f"An exception occurred:\n{context.error}\n\nTraceback:\n{tb_string}\n\nUpdate: {update_str}"
    logger.exception(message)
    
    # Optionally notify a specific user or channel about the error
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="اوه نه! یه چیزی این وسط ناجور شد 😅 ولی نگران نباش، دارم بررسیش می‌کنم! 🔍✨ \nیه کم صبر کن و چند دقیقه دیگه دوباره امتحان کن 😉\nبوس بهت 😘"
    )

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BALE_BOT_TOKEN)\
                             .base_url('https://tapi.bale.ai/')\
                             .build()
    
    # ignore old pending updates
    # application.run_polling(drop_pending_updates=True)
    
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, new_message))
    
    application.add_handler(CallbackQueryHandler(button_click))

    application.add_error_handler(error_handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()
