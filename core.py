import logging
import asyncio

from openai import AsyncOpenAI, RateLimitError

from config import OPENAPI_API_KEY, OPENAPI_URL, OPENAPI_MODEL, MAX_RETRIES

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(
    base_url=OPENAPI_URL,
    api_key=OPENAPI_API_KEY
)


async def llm(messages: list[dict]) -> str:
    """
    Sends a list of messages to the OpenAI API and returns the response content.

    Args:
        messages (list[dict]): A list of message dictionaries to send to the OpenAI API.

    Returns:
        str: The content of the response from the OpenAI API.

    Raises:
        Exception: If the maximum number of retries is reached without a successful response.
    """
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f'Attempt {attempt + 1} of {MAX_RETRIES} to get response from OpenAI API.')
            response = await openai_client.chat.completions.create(
                model=OPENAPI_MODEL,
                messages=messages
            )
            content = response.choices[0].message.content.strip()
            logger.info('Successfully received response from OpenAI API.')
            return content
        except RateLimitError:
            logger.warning('Rate limit exceeded. Retrying after 20 seconds...')
            await asyncio.sleep(20)

    logger.error('Max retries reached. Failed to translate text.')
    raise Exception('Max retries reached. Failed to translate text.')
