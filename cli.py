import argparse
import logging
import json
from datetime import datetime

from telegram import Bot
from models import User, Story, StoryScenario, Section, LLMHistory, Session, Chat, db
from config import BOT_TOKEN

logger = logging.getLogger('CLI')


def report() -> None:
    user_count = User.select().count()
    story_count = Story.select().count()
    story_scenario_count = StoryScenario.select().count()
    section_count = Section.select().count() // 2
    llm_history_count = LLMHistory.select().count()

    report = f"""
    📊 **System Report** 📊
    ---------------------------
    👤 Users:           {user_count:,}
    📖 Stories:         {story_count:,}
    🎭 Story Scenarios: {story_scenario_count:,}
    📑 Sections:        {section_count:,}
    🧠 LLM History:     {llm_history_count:,}
    ---------------------------
    ✅ Report Generated Successfully!
    """

    print(report)

def export_db_as_json(path: str = 'dump.json'):
    '''Backup important data to a JSON file.

    This function will create a JSON file with the following structure:
    {
        "users": [
            {
                "user_id": int,
                "username": str,
                "first_name": str,
                "last_name": str,
                "active": bool,
                "charge": float,
                "created_at": str,
                "stories": [
                    {
                        "id": int,
                        "user_id": int,
                        "is_end": bool,
                        "created_at": str,
                        "sections": [
                            {
                                "id": int,
                                "story": int,
                                "text": str,
                                "is_system": bool,
                                "used": bool,
                                "created_at": str
                            }
                        ]
                    }
                ]
            }
        ],
        "story_scenarios": [
            {
                "id": int,
                "story": int,
                "text": str,
                "is_system": bool,
                "created_at": str
            }
        ]
    }
    '''
    data = []
    users = User.select().order_by(User.charge)
    for user in users:
        stories = [
            {**story.as_dict, 'sections': [section.as_dict for section in story.sections]} 
            for story in Story.select().where(Story.user == user.user_id)
        ]
        data.append({
            **user.as_dict,
            'stories': stories
        })

    final = {
        'users': data,
        'story_scenarios': [story_scenario.as_dict for story_scenario in StoryScenario.select()]
    }
    with open(path, '+w') as f:
        f.write(json.dumps(final, ensure_ascii=False, indent=4))
        print(f'Data successfully exported to {path}')

def import_db_from_json(path: str = 'dump.json'):
    """
    Import data from a JSON file.
    """
    with open(path, 'r') as f:
        data = json.loads(f.read())
    
    with db.atomic():
        # Users
        for user in data['users']:
            u = User.create(
                user_id=user['user_id'],
                username=user['username'],
                first_name=user['first_name'],
                last_name=user['last_name'],
                active=user['active'],
                charge=user['charge'],
                created_at=datetime.strptime(user['created_at'], "%Y-%m-%d %H:%M:%S.%f")
            )

            # Stories
            for story in user['stories']:
                s = Story.create(
                    id=story['id'],
                    user=u.user_id,
                    is_end=story['is_end'],
                    rate=story['rate'],
                    created_at=datetime.strptime(story['created_at'], "%Y-%m-%d %H:%M:%S.%f")
                )

                # Sections
                section_data = []
                for section in story['sections']:
                    section_data.append(Section(
                        id=section['id'],
                        story=s.id,
                        text=section['text'],
                        is_system=section['is_system'],
                        used=section['used'],
                        created_at=section['created_at']
                    ))
                Section.bulk_create(section_data, batch_size=50)

        # Story scenarios
        scenarios = []
        for scenario in data['story_scenarios']:
            scenarios.append(StoryScenario(
                id=scenario['id'],
                story_id=scenario['story_id'],
                text=scenario['text'],
                is_system=scenario['is_system'],
                created_at=scenario['created_at']
            ))

        # Insert story scenarios in batches
        StoryScenario.bulk_create(scenarios, batch_size=50)

        # Reset Sequences
        db.execute_sql("SELECT setval('story_id_seq', (SELECT MAX(id) FROM story))")
        db.execute_sql("SELECT setval('section_id_seq', (SELECT MAX(id) FROM section))")
        db.execute_sql("SELECT setval('storyscenario_id_seq', (SELECT MAX(id) FROM storyscenario))")

        print('Data imported successfully')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    report_parser = subparsers.add_parser('report', help='Generate a system report')

    dump_parser = subparsers.add_parser('dump', help='Dump database to a JSON file')
    dump_parser.add_argument('--path', type=str, default='dump.json', help='Path to the output file')

    import_parser = subparsers.add_parser('import', help='Import data from a JSON file')
    import_parser.add_argument('--path', type=str, default='dump.json', help='Path to the input file')

    args = parser.parse_args()

    if args.command == 'dump':
        export_db_as_json(args.path)
    elif args.command == 'import':
        import_db_from_json(args.path)
    elif args.command == 'report':
        report()
