from decouple import config, Csv


OPENAPI_API_KEY = config('OPENAPI_API_KEY')
OPENAPI_URL = config('OPENAPI_URL', default='https://api.openai.com/v1')
OPENAPI_MODEL = config('OPENAPI_MODEL', default='gpt-4o-mini')
OPENAPI_SECONDARY_MODEL = config('OPENAPI_SECONDARY_MODEL', default='gpt-4o-mini')
# price of token per millions
INPUT_TOKEN_PRICE = config('INPUT_TOKEN_PRICE', cast=float)
OUTPUT_TOKEN_PRICE = config('OUTPUT_TOKEN_PRICE', cast=float)
MAX_RETRIES = config('MAX_RETRIES', cast=int, default=30)

STORY_COVER_GENERATION = config('STORY_COVER_GENERATION', cast=bool, default=False)
IMAGE_MODEL = config('IMAGE_MODEL', default='dall-e-3')
IMAGE_SIZE = config('IMAGE_SIZE', default='1024x1024')
IMAGE_PRICE = config('IMAGE_PRICE', cast=float, default=0.04)
IMAGE_DIR = config('IMAGE_DIR', default='images')

BALE_BOT_TOKEN = config('BALE_BOT_TOKEN')

SPONSOR_TEXT = config('SPONSOR_TEXT')
SPONSOR_URL = config('SPONSOR_URL')
DONATE_URL = config('DONATE_URL')

ADMINS_ID = config('ADMINS', cast=Csv(int), default='')
ADMIN_USERNAME = config('ADMIN_USERNAME')
LOG_CHANNEL_ID = config('LOG_CHANNEL_ID', cast=int, default=0)

WALLET_TOKEN = config('WALLET_TOKEN')

MAX_DAILY_STORY_CREATION = config('MAX_DAILY_STORY_CREATION', cast=int, default=2)
