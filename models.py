from datetime import datetime

from peewee import *

sqlite_db = SqliteDatabase('ble.db', pragmas={'journal_mode': 'wal'})


class BaseModel(Model):
    class Meta:
        database = sqlite_db


class User(BaseModel):
    user_id = BigIntegerField(primary_key=True, index=True)
    username = CharField(max_length=50, null=True)
    first_name = CharField(max_length=50, null=True)
    last_name = CharField(max_length=50, null=True)
    active = BooleanField(default=True)
    charge = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

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
            'created_at': self.created_at,
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

    def sections_history(self) -> list['Section']:
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


class Section(BaseModel):
    id = BigAutoField()
    story = ForeignKeyField(Story, backref='sections')
    text = TextField()
    is_system = BooleanField()
    used = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)


def create_tables() -> None:
    sqlite_db.create_tables([User, Story, StoryScenario, Section])

if __name__ == '__main__':
    create_tables()