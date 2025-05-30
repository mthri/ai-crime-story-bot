import random
import logging
from collections import defaultdict
from functools import wraps
from datetime import datetime, timedelta

from models import User, Story, Section, StoryScenario, Session, Chat, fn
from utils import generate_crime_story_scenarios, story_parser, AIStoryResponse,\
    calculate_token_price, ai_chat_parser, AIChatResponse, ChatCommand
from core import llm, generate_image_from_prompt, generate_story_visual_prompt
from prompts import STORY_PROMPT, CHAT_PROMPT
from config import IMAGE_PRICE, MAX_DAILY_STORY_CREATION, MAX_DAILY_CHAT_MESSAGE, MAX_SESSION_MESSAGES
from exceptions import *


logger = logging.getLogger(__name__)
session = defaultdict(lambda: {'is_processing': False})


class UserService:
    '''
    Service class for managing user-related operations.
    
    Provides functionality for retrieving, creating, and managing users
    in the system.
    '''
    
    def get_user(self, user_id: int, username: str | None = None, first_name: str | None = None,
                 last_name: str | None = None, only_active: bool = True) -> User:
        '''
        Get a user by ID or create if not exists.
        
        Args:
            user_id (int): Unique identifier for the user
            username (str, optional): User's username
            first_name (str, optional): User's first name
            last_name (str, optional): User's last name
            
        Returns:
            User: The retrieved or newly created user
            
        Raises:
            Exception: If the user exists but is deactivated
        '''
        user, created = User.get_or_create(user_id, username, first_name, last_name)
        
        if created:
            logger.info(f'Created new user with ID: {user_id}')
        else:
            logger.debug(f'Retrieved existing user with ID: {user_id}')
            
        if only_active and not user.active:
            logger.warning(f'Attempted to get deactivated user: {user_id}')
            raise UserNotActiveException(f'User {user.user_id} is deactivated.')
            
        return user
    
    def get_by_username(self, username: str) -> User:
        return User.get(User.username == username)

    def deactivate(self, user: User) -> None:
        '''
        Deactivate a user.
        
        Args:
            user (User): User to deactivate
        '''
        logger.info(f'Deactivating user: {user.user_id}')
        user.active = True
        user.save()


class StoryService:
    '''
    Service class for managing interactive story operations.
    
    Provides functionality for creating, retrieving, and progressing
    through interactive stories.
    '''
    
    async def get_by_id(self, story_id: int) -> Story | None:
        return Story.get_by_id(story_id)
    
    async def update_story_rate(self, story: Story, rate: int) -> None:
        if 0 > rate > 5:
            raise ValueError('Invalid rate value')
        
        story.rate = rate
        story.save()
    
    async def create(self, user: User) -> Story:
        '''
        Create a new story for a user.
        
        Args:
            user (User): The user for whom to create the story
            
        Returns:
            Story: The newly created story
        '''
        logger.info(f'Creating new story for user: {user.user_id}')
        qs = Story.select().where(
            (Story.user == user) &
            (Story.created_at > datetime.now() - timedelta(hours=24))
        )
        # if freemium user has reached the maximum daily story creation limit
        if  user.charge < 0.0 and qs.count() >= MAX_DAILY_STORY_CREATION:
            logger.warning(f'User {user.user_id} has reached the maximum daily story creation limit.')
            raise DailyStoryLimitExceededException(f'User {user.user_id} has reached the maximum daily story creation limit.') 
        
        return Story.create(user=user)
    
    def get_history(self, story: Story) -> list[Section]:
        '''
        Get the history of sections for a story.
        
        Args:
            story (Story): The story to retrieve history for
            
        Returns:
            list[Section]: List of sections in chronological order
        '''
        logger.debug(f'Retrieving history for story: {story.id}')
        return story.sections_histories()
    
    def as_messages(self, story: Story) -> list[dict]:
        '''
        Convert story sections to message format for the LLM.
        
        Args:
            story (Story): The story to convert
            
        Returns:
            list[dict]: Messages in the format expected by the LLM
        '''
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
                
        logger.debug(f'Converted story {story.id} to {len(messages)} messages')
        return messages
    
    def deactivate(self, story: Story) -> None:
        '''
        Mark a story as ended.
        
        Args:
            story (Story): The story to deactivate
        '''
        logger.info(f'Marking story {story.id} as ended')
        story.is_end = True
        story.save()
    
    async def start_story(self, story: Story, story_scenario: StoryScenario, user: User) -> tuple[Section, AIStoryResponse]:
        '''
        Start a new story with the given scenario.
        
        Args:
            story (Story): The story to start
            story_scenario (StoryScenario): The initial scenario for the story
            
        Returns:
            tuple[Section, AIStoryResponse]: The created section and parsed AI response
        '''
        logger.info(f'Starting story {story.id} with scenario {story_scenario.id}')
        
        scenario = f'توصیف سناریو اولیه:\n{story_scenario.text}'
        messages = [
            {'role': 'system', 'content': STORY_PROMPT % (3, )},
            {'role': 'user', 'content': scenario}
        ]
        
        logger.debug('Calling LLM for initial story content')
        for i in range(3):
            if i < 2:
                content, input_tokens, output_tokens = await llm(messages)
            else:
                logger.warning('Using secondary model for LLM request')
                content, input_tokens, output_tokens = await llm(messages, use_secondary_model=True)

            ai_response = story_parser(content)
            if ai_response:
                break
            else:
                logger.warning('Failed to parse AI response, retrying...')
        else:
            raise FailedToGenerateStoryException('Failed to generate initial story content')

        request_cost = calculate_token_price(input_tokens, output_tokens)
        user.charge -= request_cost
        user.save()
        
        # Link scenario to story
        story_scenario.story = story
        story_scenario.save()
        
        # Create sections
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
        
        logger.info(f'Story {story.id} started successfully')
        return system_section, ai_response

    async def get_full_story(self, story: Story) -> str:
        """
        Retrieve the full story text for a given story by combining all its sections.
        
        Args:
            story (Story): The story to retrieve the full story text for
            
        Returns:
            str: The full story text
        """
        sections = Section.select().where(Section.story == story)
        full_story = ''
        for section in sections:
            try:
                parsed_section = story_parser(section.text)
                if parsed_section:
                    full_story += parsed_section.story + '\n'
            except Exception:
                pass
        
        return full_story

    async def generate_story_cover(self, story: Story, user: User | None = None) -> str:
        '''
        Generate a cover image for a given story by calling the LLM for visual prompts and generating an image from the response.
        
        Args:
            story (Story): The story to generate a cover image for
            user (User): The user for which to charge the cost of generating the image
            
        Returns:
            str: The path to the generated image
        '''
        logger.info(f'Generating cover for story {story.id}')
        full_story = await self.get_full_story(story)
        content, input_tokens, output_tokens = await generate_story_visual_prompt(full_story)
        image_path = await generate_image_from_prompt(content)
        logger.info(f'Generated cover image for story {story.id} at {image_path}')
        
        request_cost = calculate_token_price(input_tokens, output_tokens)
        if not user:
            user = story.user
        user.charge -= request_cost + IMAGE_PRICE
        user.save()
        
        return image_path

    def create_scenario(self, story: Story, text: str) -> StoryScenario:
        '''
        Create a user-defined scenario for a story.
        
        Args:
            story (Story): The story to create the scenario for
            text (str): The scenario text
            
        Returns:
            StoryScenario: The created scenario
        '''
        logger.info(f'Creating user-defined scenario for story {story.id}')
        return StoryScenario.create(
            story=story,
            text=text,
            is_system=False
        )

    async def generate_ai_scenarios(self) -> list[StoryScenario]:
        '''
        Generate new AI-created scenarios.
        
        Returns:
            list[StoryScenario]: List of newly created scenarios
        '''
        logger.info('Generating new AI scenarios')
        scenarios = []
        _scenarios = await generate_crime_story_scenarios()
        
        for scenario in _scenarios:
            scenarios.append(
                StoryScenario.create(
                    story=None,
                    text=scenario,
                    is_system=True
                )
            )
            
        logger.info(f'Generated {len(scenarios)} new AI scenarios')
        return scenarios

    async def get_unused_scenarios(self, limit: int = 4) -> list[StoryScenario]:
        '''
        Get unused system-generated scenarios.
        
        Args:
            limit (int, optional): Maximum number of scenarios to return. Defaults to 4.
            
        Returns:
            list[StoryScenario]: List of unused scenarios
        '''
        logger.debug(f'Retrieving up to {limit} unused scenarios')
        
        # Query for unused scenarios
        query = (
            StoryScenario
            .select()
            .where(
                (StoryScenario.story == None) &
                (StoryScenario.is_system == True)
            )
            .limit(100)
        )
        scenarios = list(query)
        
        # Generate new scenarios if needed
        if len(scenarios) < limit:
            logger.info(f'Only {len(scenarios)} scenarios available, generating more')
            scenarios = await self.generate_ai_scenarios()
        
        # Randomize and limit results
        random.shuffle(scenarios)
        return scenarios[:limit]

    async def create_section(self, user: User, story: Story, choice: int) -> tuple[Section, AIStoryResponse]:
        '''
        Create a new section in the story based on user choice.
        
        Args:
            story (Story): The story to add a section to
            choice (int): The user's choice number
            
        Returns:
            tuple[Section, AIStoryResponse]: The created section and parsed AI response
        '''
        logger.info(f'Creating new section for story {story.id} with choice {choice}')
        
        # Prepare messages for LLM
        messages = self.as_messages(story)
        messages.append({
            'role': 'user',
            'content': str(choice)
        })
        
        # Get AI response
        logger.debug('Calling LLM for next story section')
        for i in range(3):
            if i < 2:
                content, input_tokens, output_tokens = await llm(messages)
            else:
                logger.warning('Using secondary model for LLM request')
                content, input_tokens, output_tokens = await llm(messages, use_secondary_model=True)

            ai_response = story_parser(content)
            if ai_response:
                break
            else:
                logger.warning('Failed to parse AI response, retrying...')
        else:
            raise FailedToGenerateStoryException('Failed to generate story section content')
        
        request_cost = calculate_token_price(input_tokens, output_tokens)
        user.charge -= request_cost
        user.save()
        logger.debug(f'Story end status: {ai_response.is_end}')

        # Create sections in database
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
        '''
        Get a scenario by ID.
        
        Args:
            scenario_id (int): ID of the scenario to retrieve
            
        Returns:
            StoryScenario: The retrieved scenario
        '''
        logger.debug(f'Retrieving scenario with ID: {scenario_id}')
        scenario = StoryScenario.get_by_id(scenario_id)
        return scenario
    
    def get_section(self, section_id: int) -> Section:
        '''
        Get a section by ID.
        
        Args:
            section_id (int): ID of the section to retrieve
            
        Returns:
            Section: The retrieved section
        '''
        logger.debug(f'Retrieving section with ID: {section_id}')
        section = Section.get_by_id(section_id)
        return section
    
    def mark_section_as_used(self, section: Section) -> None:
        '''
        Mark a section as used.
        
        Args:
            section (Section): The section to mark
        '''
        logger.debug(f'Marking section {section.id} as used')
        section.used = True
        section.save()

    async def get_unused_section(self, section_id: int) -> Section | None:
        '''
        Get an unused section by ID if it exists and is part of an active story.
        
        Args:
            section_id (int): ID of the section to retrieve
            
        Returns:
            Section | None: The retrieved section or None if not found
        '''
        logger.debug(f'Looking for unused section with ID: {section_id}')
        section = (
            Section
            .select()
            .join(Story)
            .where(
                (Section.id == section_id) &
                (Section.used == False) &
                (Story.is_end == False)
            )
            .get_or_none()
        )
        
        if section:
            logger.debug(f'Found unused section: {section_id}')
        else:
            logger.debug(f'No unused section found with ID: {section_id}')
            
        return section
    
    async def deactivate_active_stories(self, user: User) -> None:
        '''
        Mark all active stories for a user as ended.
        
        Args:
            user (User): The user whose stories to deactivate
        '''
        logger.info(f'Deactivating all active stories for user: {user.user_id}')
        query = Story.update(is_end=True).where((Story.user == user) & (Story.is_end == False))
        affected_rows = query.execute()
        logger.info(f'Deactivated {affected_rows} stories for user: {user.user_id}')

    async def damage_report(self, user: User) -> tuple[int,int,float]:
        '''
        Calculate the damage report for a user.
        
        Args:
            user (User): The user to calculate the damage report for
            
        Returns:
            tuple[int,int,float]: Number of stories, sections, and charge balance
        '''
        logger.info(f'Calculating damage report for user: {user.user_id}')
        
        # Count active stories
        stories_count = Story.select().where(Story.user == user).count()

        section_count = (
            Section
            .select(fn.COUNT(Section.id))
            .join(Story)
            .join(User)
            .where(User.user_id == user.user_id)
            .scalar()
        )        
        
        logger.info(f'Damage report for user {user.user_id}')
        return stories_count, section_count, user.charge


class ChatService:
    '''
    Service for handling user chat interactions, managing sessions, and processing messages with the LLM.
    '''
    
    async def __get_session_history(self, session: Session) -> list[Chat]:
        '''
        Get the chat history for a session.
        
        Args:
            session (Session): The session for which to retrieve the chat history
            
        Returns:
            list[Chat]: The chat history
        '''
        logger.info(f'Getting session history for session {session.id}')
        return session.chat_histories()
    
    async def __start_new_session(self, user: User) -> Session:
        # deactivate previous session
        '''
        Starts a new session for the given user, deactivating any active session
        
        Args:
            user (User): The user to start a new session for
        
        Returns:
            Session: The newly created session
        '''
        logger.info(f'Starting new session for user {user.user_id}')
        Session.update(active=False).where(Session.user == user).execute()
        
        query = Chat.select().where(
            (Chat.user == user) &
            (Chat.is_system == False) &
            (Chat.created_at > datetime.now() - timedelta(hours=24))
        )
        # if freemium user has reached the maximum daily chat message limit
        if  user.charge < 0.0 and query.count() >= MAX_DAILY_CHAT_MESSAGE:
            logger.info(f'User {user.user_id} has reached the maximum daily chat message limit.')
            raise DailyChatLimitExceededException(f'User {user.user_id} has reached the maximum daily chat message limit.')
        
        # create new session
        session = Session.create(user=user)
        chat = Chat.create(
            session=session,
            user=user,
            text=CHAT_PROMPT,
            is_system=True
        )
        return session

    async def __get_current_session(self, user: User) -> Session | None:
        '''
        Retrieve the current active session for a user.

        Args:
            user (User): The user for whom to retrieve the active session.

        Returns:
            Session | None: The active session if it exists, otherwise None.
        '''

        logger.info(f'Getting current session for user {user.user_id}')
        session = Session.select().where((Session.user == user) & (Session.active == True))
        if session.exists():
            return session.get()
        return None

    async def __chat_history_as_messages(self, session: Session) -> list[dict]:
        '''
        Convert chat history for a session to message format for the LLM.

        Args:
            session (Session): The session for which to retrieve the chat history.

        Returns:
            list[dict]: Messages in the format expected by the LLM.
        '''
        logger.info(f'Converting chat history for session {session.id}')
        chat_histories = await self.__get_session_history(session)
        messages = []
        for index, message in enumerate(chat_histories):
            if message.is_system:
                messages.append({
                    'role': 'assistant' if index else 'system',
                    'content': message.text
                })
            else:
                messages.append({
                    'role': 'user',
                    'content': message.text
                })
        return messages

    async def deactivate_current_session(self, user: User) -> None:
        '''
        Deactivate the current active session for a user.

        Args:
            user (User): The user whose active session should be deactivated.
        '''
        logger.info(f'Deactivate active session for user {user.user_id}')
        session = await self.__get_current_session(user)
        if session:
            session.active = False
            session.save()

    async def chat(self, user: User, text: str) -> AIChatResponse:
        '''
        Process a user's chat message and respond accordingly.

        Args:
            user (User): The user who sent the message
            text (str): The message text

        Returns:
            AIChatResponse: The parsed AI response

        Raises:
            ValueError: If the message text is empty
        '''
        if not text:
            raise ValueError('Text cannot be empty')
        
        logger.info(f'Processing chat message from user {user.user_id}')
        session = await self.__get_current_session(user)
        if not session:
            session = await self.__start_new_session(user)
        
        messages = await self.__chat_history_as_messages(session)

        if len(messages) > MAX_SESSION_MESSAGES:
            logger.warning(f'Session {session.id} has more than {MAX_SESSION_MESSAGES} messages!, deactivating session')
            session.active = False
            session.save()

        messages.append({
            'role': 'user',
            'content': text
        })

        logger.info(f'Sending messages to LLM for processing')
        for i in range(3):
            if i < 2:
                content, input_tokens, output_tokens = await llm(messages)
            else:
                logger.warning('Using secondary model for LLM request')
                content, input_tokens, output_tokens = await llm(messages, use_secondary_model=True)

            ai_response = ai_chat_parser(content)
            if ai_response:
                break
            else:
                logger.warning('Failed to parse AI response, retrying...')
        else:
            raise FailedToGenerateChatException('Failed to generate chat response')

        request_cost = calculate_token_price(input_tokens, output_tokens)
        user.charge -= request_cost
        user.save()
        
        Chat.create(session=session, user=user, text=text, is_system=False)
        Chat.create(session=session, user=user, text=content, is_system=True)

        return ai_response


user_service = UserService()


def user_lock(user):
    """Locks the user session by setting the 'is_processing' flag to True.

    Args:
        user (str): The identifier of the user to be locked.

    Side Effects:
        Updates the global `session` dictionary.
    """
    session[user]['is_processing'] = True
    logger.info(f'User {user} has been locked for processing.')


def user_unlock(user):
    """Unlocks the user session by setting the 'is_processing' flag to False.

    Args:
        user (str): The identifier of the user to be unlocked.

    Side Effects:
        Updates the global `session` dictionary.
    """
    session[user]['is_processing'] = False
    logger.info(f'User {user} has been unlocked.')


def is_user_lock(user):
    """Checks if the user session is currently locked.

    Args:
        user (str): The identifier of the user.

    Returns:
        bool: True if the user session is locked, False otherwise.
    """
    return session[user]['is_processing']


def asession_lock(func, only_private=True):
    """Decorator that prevents concurrent execution of an async function 
    for the same user by implementing a session lock.

    If the user is already processing another request, the function call is skipped.

    Args:
        func (Callable): The async function to be wrapped.

    Returns:
        Callable: The wrapped async function with session locking.

    Side Effects:
        - Locks the user before execution.
        - Unlocks the user after execution.
    """
    @wraps(func)
    async def wrapped(update, *args, **kwargs):
        if only_private and update.message and update.message.chat.type != 'private':
            logger.info(f'Ignored non-private message')
            return None
        
        user = user_service.get_user(
            update.effective_user.id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name
        )

        if is_user_lock(user):
            logger.warning(f'User {user} is already locked, skipping execution.')
            return None
        
        user_lock(user)
        await func(update, *args, user=user, **kwargs)
        user_unlock(user)

    return wrapped


def ignore_non_private(func):
    @wraps(func)
    async def wrapped(update, *args, **kwargs):
        """Decorator that ignores non-private messages.

        Args:
            update (Update): Telegram update object
            *args: Arguments to be passed to the wrapped function
            **kwargs: Keyword arguments to be passed to the wrapped function

        Returns:
            Any: The result of the wrapped function if the message is private,
                otherwise None
        """
        if update.message and update.message.chat.type != 'private':
            logger.info(f'Ignored non-private message')
            return None
        return await func(update, *args, **kwargs)
    return wrapped