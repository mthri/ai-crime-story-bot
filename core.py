import logging
import asyncio
import json

from openai import AsyncOpenAI, RateLimitError

from config import OPENAPI_API_KEY, OPENAPI_URL, OPENAPI_MODEL, MAX_RETRIES
from models import LLMHistory

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(
    base_url=OPENAPI_URL,
    api_key=OPENAPI_API_KEY
)


async def llm(messages: list[dict]) -> tuple[str, int, int]:
    """
    Sends a list of messages to the OpenAI API and returns the response content along with token usage.

    Args:
        messages (list[dict]): A list of message dictionaries to send to the OpenAI API.

    Returns:
        tuple[str, int, int]: A tuple containing the content of the response, the number of input tokens used, and the number of output tokens used.

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
            logger.info('Successfully received response from OpenAI API.')
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            content = response.choices[0].message.content.strip()
            LLMHistory.create(
                model=OPENAPI_MODEL,
                prompt=json.dumps(messages, ensure_ascii=False),
                response=content
            )
            return content, input_tokens, output_tokens
        except RateLimitError:
            logger.warning('Rate limit exceeded. Retrying after 20 seconds...')
            await asyncio.sleep(20)

    logger.error('Max retries reached. Failed to translate text.')
    raise Exception('Max retries reached. Failed to translate text.')
