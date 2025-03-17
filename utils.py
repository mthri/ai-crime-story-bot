import json
from dataclasses import dataclass
import logging

from core import llm
from prompts import GENERATE_CRIME_STORY_SCENARIOS_PROMPT
from config import INPUT_TOKEN_PRICE, OUTPUT_TOKEN_PRICE

logger = logging.getLogger(__name__)

@dataclass
class Option:
    id: int
    text: str

@dataclass
class AIStoryResponse:
    title: str
    story: str
    options: list[Option]
    is_end: bool
    raw_data: str

def calculate_token_price(input_tokens: int, output_tokens: int) -> float:
    """Calculates the total token price based on input and output token usage.

    Args:
        input_tokens (int): Number of input tokens.
        output_tokens (int): Number of output tokens.

    Returns:
        float: The total calculated price.
    """
    input_cost = (input_tokens * INPUT_TOKEN_PRICE) / 1_000_000
    output_cost = (output_tokens * OUTPUT_TOKEN_PRICE) / 1_000_000
    return input_cost + output_cost

async def generate_crime_story_scenarios() -> list[str]:
    """Generates crime story scenarios using an AI model.

    Returns:
        list[str]: A list of generated story scenarios.
    """
    messages = [
        {'role': 'system', 'content': GENERATE_CRIME_STORY_SCENARIOS_PROMPT},
        {'role': 'user', 'content': 'سناریو ها رو تولید کن'},
    ]
    content, input_tokens, output_tokens = await llm(messages)
    #TODO request_cost?
    request_cost = calculate_token_price(input_tokens, output_tokens)

    return [scenario for scenario in content.split('\n') if scenario and len(scenario) > 10]

#TODO handle JSON pars error
def story_parser(text: str) -> AIStoryResponse:
    """Parses a JSON-formatted story response into an AIStoryResponse object.

    Args:
        text (str): The raw JSON string containing the story.

    Returns:
        AIStoryResponse: Parsed story data.
    """
    try:
        json_data = json.loads(text.removeprefix('```json').removesuffix('```'))
    except json.decoder.JSONDecodeError as e:
        logging.error(str(e))
        return None

    options = [Option(id=int(key), text=value) for key, value in json_data['options'].items()]

    return AIStoryResponse(
        title=json_data['title'],
        story=json_data['story'],
        options=options,
        is_end=json_data['is_end'],
        raw_data=text
    )

def replace_english_numbers_with_farsi(text: str | int) -> str:
    """Replaces English numbers in a string with Farsi numbers.

    Args:
        text (str): The input string containing English numbers.

    Returns:
        str: The string with English numbers replaced by Farsi numbers.
    """
    if isinstance(text, int):
        text = str(text)
    english_to_farsi = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return text.translate(english_to_farsi)
