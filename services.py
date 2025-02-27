import random

from models import User, Story, Section, StoryScenario
from utils import generate_crime_story_scenarios
from core import llm
from utils import story_parser, Option, AIStoryResponse
from prompts import STORY_PROMPT


class UserService:
    def __init__(self):
        pass

    def get_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
        user, created = User.get_or_create(user_id, username, first_name, last_name)
        if not user.active:
            raise Exception(f'User {user.user_id} is deactivate.')
        return user

    def deactivate(self, user: User) -> None:
        user.active = True
        user.save()
    
#TODO make it awaitable and user async peewee
class StoryService:
    def __init__(self):
        pass

    def create(self,user: User) -> Story:
        #TODO must have one active story
        return Story.create(user=user)
    
    def get_history(self, story: Story) -> list[Section]:
        return story.sections_history()
    
    def as_messages(self, story: Story) -> list[dict]:
        messages = []
        sections = self.get_history(story)
        for index, section in enumerate(sections):
            if section.is_system:
                messages.append({
                    'role': 'assistant' if index else 'system',
                    'content': section.text
                })
            else:
                messages.append({
                    'role': 'user',
                    'content': section.text
                })
        return messages
    
    def deactivate(self, story: Story) -> None:
        story.is_end = True
        story.save()
    
    def start_story(self, story: Story, story_scenario: StoryScenario) -> tuple[Section,AIStoryResponse]:
        scenario = f'توصیف سناریو اولیه:\n{story_scenario.scenario}'
        messages = [
            {'role': 'system','content': STORY_PROMPT%(3,3)},
            {'role': 'user','content': scenario}
        ]
        content = llm(messages)
        ai_response = story_parser(content)
        
        story_scenario.story = story
        story_scenario.save()
        
        system_section = Section.create(
            story=story,
            text=STORY_PROMPT,
            is_system=True
        )
        user_section = Section.create(
            story=story,
            text=scenario,
            is_system=False
        )
        system_section = Section.create(
            story=story,
            text=ai_response.raw_data,
            is_system=True
        )

        return system_section, ai_response

    def create_scenario(self, story: Story, text: str) -> StoryScenario:
        return StoryScenario.create(
            story=story,
            scenario=text,
            is_system=False
        )

    def generate_ai_scenarios(self) -> list[StoryScenario]:
        scenarios = []
        for scenario in generate_crime_story_scenarios():
            scenarios.append(
                    StoryScenario.create(
                    story=None,
                    scenario=scenario,
                    is_system=True
                )
            )
        return scenarios

    def get_unused_scenarios(self, limit: int = 4) -> list[StoryScenario]:
        #TODO limit created_at, get 100 return shuffle limit
        query = (
            StoryScenario
            .select()
            .where(
                (StoryScenario.story == None)
                & (StoryScenario.is_system == True)
            )
            .limit(100)
        )
        scenarios = list(query)
        
        if len(scenarios) < limit:
            scenarios = self.generate_ai_scenarios()
        
        random.shuffle(scenarios)
        return scenarios[:limit]

    def create_section(self, story: Story, choice: int) -> tuple[Section,AIStoryResponse]:
        messages = self.as_messages(story)
        messages.append({
            'role': 'user',
            'content': str(choice)
        })
        content = llm(messages)
        ai_response = story_parser(content)
        print(f'IS END {ai_response.is_end}')

        user_section = Section.create(
            story=story,
            text=str(choice),
            is_system=False
        )
        system_section = Section.create(
            story=story,
            text=ai_response.raw_data,
            is_system=True
        )

        return system_section, ai_response

    def get_scenario(self, scenario_id: int) -> StoryScenario:
        scenario = StoryScenario.get_by_id(scenario_id)
        return scenario
    
    def get_section(self, section_id: int) -> Section:
        #TODO must not used
        section = Section.get_by_id(section_id)
        return section
    
    def mark_section_as_used(self, section: Section) -> None:
        pass