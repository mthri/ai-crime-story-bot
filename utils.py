import json
from dataclasses import dataclass
from collections import defaultdict

from core import llm
from prompts import GENERATE_CRIME_STORY_SCENARIOS_PROMPT
from config import INPUT_TOKEN_PRICE, OUTPUT_TOKEN_PRICE


session = defaultdict(dict)

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
    input_cost = (input_tokens * INPUT_TOKEN_PRICE) / 1_000_000
    output_cost = (output_tokens * OUTPUT_TOKEN_PRICE) / 1_000_000
    return input_cost + output_cost

async def generate_crime_story_scenarios() -> list[str]:
    messages = [
        {'role': 'system', 'content': GENERATE_CRIME_STORY_SCENARIOS_PROMPT},
        {'role': 'user', 'content': 'سناریو ها رو تولید کن'},
    ]
    content, input_tokens, output_tokens = await llm(messages)
    request_cost = calculate_token_price(input_tokens, output_tokens)
    return [scenario for scenario in content.split('\n') if scenario]

def story_parser(text: str) -> AIStoryResponse:
    _text = text.replace('```json', '').replace('```', '')
    json_data = json.loads(_text)

    options = []
    for key, value in json_data['options'].items():
        options.append(Option(id=int(key), text=value))

    story = AIStoryResponse(
        title=json_data['title'],
        story=json_data['story'],
        options=options,
        is_end=json_data['is_end'],
        raw_data=text
    )
    
    return story
