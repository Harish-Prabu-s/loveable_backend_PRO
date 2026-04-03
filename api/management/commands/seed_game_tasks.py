from django.core.management.base import BaseCommand
from api.models import QuestionBank

class Command(BaseCommand):
    help = 'Seeds the QuestionBank with initial Truths and Dares'

    def handle(self, *args, **kwargs):
        tasks = [
            {'type': 'truth', 'text': 'What is the most embarrassing thing in your room right now?'},
            {'type': 'truth', 'text': 'Have you ever lied to get out of hanging out with someone?'},
            {'type': 'truth', 'text': 'Who is your secret crush?'},
            {'type': 'truth', 'text': 'What is the weirdest dream you have ever had?'},
            {'type': 'dare', 'text': 'Do your best impression of another player until your next turn.'},
            {'type': 'dare', 'text': 'Show the last photo you took on your phone.'},
            {'type': 'dare', 'text': 'Let another player tweet/post something from your account.'},
            {'type': 'challenge', 'text': 'Staring contest with the person to your left. Loser takes a penalty.'}
        ]
        
        count = 0
        for t in tasks:
            obj, created = QuestionBank.objects.get_or_create(
                question_type=t['type'],
                text=t['text'],
                defaults={'difficulty': 1}
            )
            if created:
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} new game tasks.'))
