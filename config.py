from decouple import config


OPENAPI_API_KEY = config('OPENAPI_API_KEY')
OPENAPI_URL = config('OPENAPI_URL', default='https://api.openai.com/v1')
OPENAPI_MODEL = config('OPENAPI_MODEL', default='gpt-4o-mini')
MAX_RETRIES = config('MAX_RETRIES', cast=int, default=30)

BALE_BOT_TOKEN = config('BALE_BOT_TOKEN')

