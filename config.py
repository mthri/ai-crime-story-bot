from decouple import config, Csv


OPENAPI_API_KEY = config('OPENAPI_API_KEY')
OPENAPI_URL = config('OPENAPI_URL', default='https://api.openai.com/v1')
OPENAPI_MODEL = config('OPENAPI_MODEL', default='gpt-4o-mini')
# price of token per millions
INPUT_TOKEN_PRICE = config('INPUT_TOKEN_PRICE', cast=float)
OUTPUT_TOKEN_PRICE = config('OUTPUT_TOKEN_PRICE', cast=float)
MAX_RETRIES = config('MAX_RETRIES', cast=int, default=30)

IMAGE_MODEL = config('IMAGE_MODEL', default='dall-e-3')
IMAGE_SIZE = config('IMAGE_SIZE', default='1024x1024')
IMAGE_PRICE = config('IMAGE_PRICE', cast=float, default=0.04)
IMAGE_DIR = config('IMAGE_DIR', default='images')

BALE_BOT_TOKEN = config('BALE_BOT_TOKEN')

SPONSOR_TEXT = config('SPONSOR_TEXT')
SPONSOR_URL = config('SPONSOR_URL')

ADMINS = config('ADMINS', cast=Csv(int), default='')
LOG_CHANNEL_ID = config('LOG_CHANNEL_ID', cast=int, default=0)