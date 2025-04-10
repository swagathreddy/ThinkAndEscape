from django.core.management.base import BaseCommand
from chatbot.models import Theme, Room, Element, Answer

class Command(BaseCommand):
    help = 'Populate the database with The Forgotten Labyrinth theme'

    def handle(self, *args, **kwargs):
        # Create The Forgotten Labyrinth theme
        theme, created = Theme.objects.get_or_create(
            name='The Forgotten Labyrinth', 
            defaults={'description': 'Trapped within an ancient labyrinth with walls that pulse with an eerie, sentient energy. Faint whispers echo through stone corridors, challenging you to solve mysterious puzzles to escape.'}
        )

        # Create Labyrinth room
        room, _ = Room.objects.get_or_create(
            theme=theme,
            name='Labyrinth Chamber', 
            defaults={'description': 'A mysterious chamber within the ancient labyrinth. Three enigmatic objects stand before you: a stone mirror, a silver key, and a glowing inscription. Each holds a challenge that must be solved to progress.'}
        )

        # Define element details
        element_data = [
            {
                'name': 'stone_mirror',
                'puzzle': 'I never speak, but I can answer any question. What am I?',
                'hint': 'Look closely at your reflection.'
            },
            {
                'name': 'silver_key',
                'puzzle': 'I am not alive, but I grow. I don\'t have lungs, but I need air. What am I?',
                'hint': 'Think about something that requires oxygen but isn\'t living.'
            },
            {
                'name': 'glowing_inscription',
                'puzzle': 'I am a two-digit number. If you reverse my digits, I become 18 less than my original value. What number am I?',
                'hint': 'Try working out the math relationship between the original and reversed number.'
            }
        ]

        # Create elements and answers
        for element_info in element_data:
            element, _ = Element.objects.get_or_create(
                room=room,
                name=element_info['name'],
                defaults={
                    'puzzle': element_info['puzzle'],
                    'hint': element_info['hint'],
                    'solved': False
                }
            )

            # Determine answers based on element name
            answers = {
                'stone_mirror': ['mirror'],
                'silver_key': ['fire'],
                'glowing_inscription': ['27']
            }

            # Create answers
            for ans in answers.get(element_info['name'], []):
                Answer.objects.get_or_create(
                    element=element,
                    answer=ans
                )

        self.stdout.write(self.style.SUCCESS('Successfully added The Forgotten Labyrinth theme'))