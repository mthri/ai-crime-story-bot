import logging
import asyncio
import json

from openai import AsyncOpenAI, RateLimitError

from config import OPENAPI_API_KEY, OPENAPI_URL, OPENAPI_MODEL, MAX_RETRIES

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('core')

openai_client = AsyncOpenAI(
    base_url=OPENAPI_URL,
    api_key=OPENAPI_API_KEY
)


async def llm(messages: list[dict]) -> str:
    for _ in range(MAX_RETRIES):
        try:
            response = await openai_client.chat.completions.create(
                model=OPENAPI_MODEL,
                messages=messages
            )
            with open('llm2.log', '+a') as f:
                f.write('-' * 20)
                f.write(json.dumps(messages, ensure_ascii=False, indent=4))
                f.write('-' * 20 + '\n')
            
            content = response.choices[0].message.content.strip()
            
            with open('llm.log', 'a') as f:
                f.write('\n' + content + '\n' + '-' * 50)
            
            return content
        except RateLimitError:
            logger.warning('Rate limit exceeded. Retrying after 20 seconds...')
            await asyncio.sleep(20)

    raise Exception('Max retries reached. Failed to translate text.')

