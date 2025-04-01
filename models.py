from datetime import datetime
import uuid

from peewee import *

from config import USE_SQLITE


if USE_SQLITE:
    db = SqliteDatabase('ble.db', pragmas={'journal_mode': 'wal'})
else:
    from config import (
        PGDB_USER,
        PGDB_PASS,
        PGDB_NAME,
        PGDB_HOST,
        PGDB_PORT
    )
    db = PostgresqlDatabase(PGDB_NAME, user=PGDB_USER, password=PGDB_PASS,
                            host=PGDB_HOST, port=PGDB_PORT)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    user_id = BigIntegerField(primary_key=True, index=True)
    username = CharField(max_length=50, null=True)
    first_name = CharField(max_length=255, null=True)
    last_name = CharField(max_length=255, null=True)
    active = BooleanField(default=True)
    charge = FloatField(default=0)
    created_at = DateTimeField(default=datetime.now)

    def __hash__(self):
        return self.user_id

    @property
    def as_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'last_name': self.last_name,
            'active': self.active,
            'charge': self.charge,
            'created_at': str(self.created_at),
        }

    @classmethod
    def get_or_create(cls, user_id: int, username: str = None,
                      first_name: str = None, last_name: str = None) -> tuple['User', bool]:
        user = cls.select().where(User.user_id == user_id)
        if user.exists():
            return user.first(), False
        
        user = cls.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        return user, True


class Story(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, null=True)
    is_end = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    rate = IntegerField(null=True)

    @property
    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'user': self.user.user_id,
            'is_end': self.is_end,
            'created_at': str(self.created_at),
            'rate': self.rate
        }

    def sections_histories(self) -> list['Section']:
        query = (
            self.sections
            .order_by(Section.created_at)
        )
        return list(query)


class StoryScenario(BaseModel):
    id = BigAutoField()
    story = ForeignKeyField(Story, on_delete=None, null=True)
    text = TextField()
    is_system = BooleanField()
    created_at = DateTimeField(default=datetime.now)

    @property
    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'story': self.story.id if self.story else None,
            'text': self.text,
            'is_system': self.is_system,
            'created_at': str(self.created_at)
        }


class Section(BaseModel):
    id = BigAutoField()
    story = ForeignKeyField(Story, backref='sections')
    text = TextField()
    is_system = BooleanField()
    used = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)

    @property
    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'story': self.story.id,
            'text': self.text,
            'is_system': self.is_system,
            'used': self.used,
            'created_at': str(self.created_at)
        }


class LLMHistory(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, null=True)
    model = CharField(max_length=50)
    prompt = TextField()
    response = TextField()
    created_at = DateTimeField(default=datetime.now)


class Session(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, null=True)
    session_id = CharField(max_length=32, default=uuid.uuid4)
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)

    def chat_histories(self) -> list['Chat']:
        query = (
            self.chats
            .order_by(Section.created_at)
        )
        return list(query)


class Chat(BaseModel):
    id = BigAutoField()
    session = ForeignKeyField(Session, backref='chats')
    user = ForeignKeyField(User, null=True)
    text = TextField()
    is_system = BooleanField()
    created_at = DateTimeField(default=datetime.now)


def create_tables() -> None:
    db.create_tables([User, Story, StoryScenario, Section, LLMHistory])

if __name__ == '__main__':
    create_tables()