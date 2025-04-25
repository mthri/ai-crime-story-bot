import logging
import asyncio
import json
import time
from pathlib import Path

import aiohttp
import aiofiles
from openai import AsyncOpenAI, RateLimitError, InternalServerError
from aiohttp_socks import ProxyConnector

from config import (
    OPENAPI_API_KEY,
    OPENAPI_URL,
    OPENAPI_MODEL,
    MAX_RETRIES,
    IMAGE_MODEL,
    IMAGE_SIZE,
    IMAGE_DIR,
    OPENAPI_SECONDARY_MODEL,
    LOG_LLM,
)
from models import LLMHistory
from prompts import SUMMARIZE_STORY_FOR_IMAGE
from exceptions import *

logger = logging.getLogger(__name__)
IMAGE_DIR = Path(IMAGE_DIR)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
 
openai_client = AsyncOpenAI(
    base_url=OPENAPI_URL,
    api_key=OPENAPI_API_KEY
)


async def download_image(image_url: str) -> str:
    """Downloads an image from the given URL and saves it to a file in the specified directory.

    Args:
        image_url (str): The URL of the image to download.

    Returns:
        str: The path to the downloaded image file.
    """
    filename = IMAGE_DIR / f'ai_image_{int(time.time() * 1000)}.png'
    logger.info(f'Downloading image from: {image_url}')
    # connector = ProxyConnector.from_url('socks5://127.0.0.1:2080') connector=connector
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                async with aiofiles.open(filename, 'wb') as f:
                    await f.write(await response.read())
                logger.info(f'Image saved at: {filename}')
                return str(filename)
            else:
                logger.error(f'Failed to download image: {response.status}')

async def llm(messages: list[dict], use_secondary_model: bool = False) -> tuple[str, int, int]:
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
        model = OPENAPI_MODEL if not use_secondary_model else OPENAPI_SECONDARY_MODEL
        try:
            logger.info(f'Attempt {attempt + 1} of {MAX_RETRIES} to get response from OpenAI API.')
            response = await openai_client.chat.completions.create(
                model=model,
                messages=messages
            )
            logger.info(f'Successfully received response from OpenAI API.[{model}]')
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            content = response.choices[0].message.content.strip()
            if LOG_LLM:
                LLMHistory.create(
                    model=OPENAPI_MODEL,
                    prompt=json.dumps(messages, ensure_ascii=False),
                    response=content
                )
            return content, input_tokens, output_tokens
        #TODO or balance is too low
        except RateLimitError:
            logger.warning('Rate limit exceeded. Retrying after 2 seconds...')
            await asyncio.sleep(2)
        except InternalServerError:
            logger.warning('Internal server error. Retrying after 2 seconds...')
            await asyncio.sleep(2)
    
    logger.error('Max retries reached. Failed to translate text.')
    raise NotEnoughCreditsException('Max retries reached. Failed to translate text.')

async def generate_image_from_prompt(prompt: str) -> str:
    """
    Generates an image from a given prompt using the OpenAI API.

    Args:
        prompt (str): The prompt to generate an image from.

    Returns:
        str: The path to the generated image file.

    Raises:
        Exception: If the maximum number of retries is reached without a successful response.
    """
    if len(prompt) > 1000:
        prompt = prompt[:1000]

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f'Attempt {attempt + 1} of {MAX_RETRIES} to get image from OpenAI API.')
            response = await openai_client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                n=1,
                size=IMAGE_SIZE
            )
            logger.info('Successfully received response from OpenAI API.')
            image_url = response.data[0].url
            if LOG_LLM:
                LLMHistory.create(
                    model=IMAGE_MODEL,
                    prompt=prompt,
                    response=image_url
                )
            image_path = await download_image(image_url)
            return image_path
        except RateLimitError:
            logger.warning('Rate limit exceeded. Retrying after 2 seconds...')
            await asyncio.sleep(2)
        except InternalServerError:
            logger.warning('Internal server error. Retrying after 2 seconds...')
            await asyncio.sleep(2)

    logger.error('Max retries reached. Failed to generate image.')
    raise FailedToGenerateImageException('Max retries reached. Failed to generate image.')

async def generate_story_visual_prompt(story_text: str) -> tuple[str, int, int]:
    """
    Generates a visual prompt for a story based on the given text.

    Args:
        story_text (str): The text of the story.

    Returns:
        tuple[str, int, int]: A tuple containing the generated prompt, the number of input tokens used, and the number of output tokens used.
    """
    if len(story_text) > 2000:
        story_text = story_text[:2000]
        logger.warning('Story text is too long. Truncating to 2000 characters...')

    prompt = SUMMARIZE_STORY_FOR_IMAGE.format(story_text=story_text)
    messages = [
        {'role': 'system', 'content': 'You are an expert in visual storytelling..'},
        {'role': 'user', 'content': prompt}
    ]
    content, input_tokens, output_tokens = await llm(messages)

    return content, input_tokens, output_tokens


async def get_account_credit() -> float:
    raise NotImplementedError
