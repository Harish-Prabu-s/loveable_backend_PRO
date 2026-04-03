import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from api.models import Profile, Wallet, LeagueStats, Follow, Story, StoryLike, CallSession
from api.modules.monetization.services import seed_default_rules

# 50 realistic names split by gender
MALE_NAMES = [
    'Arjun Sharma', 'Rohan Mehra', 'Vikram Singh', 'Aditya Kumar', 'Rahul Nair',
    'Karan Kapoor', 'Siddharth Joshi', 'Manish Patel', 'Deepak Reddy', 'Nikhil Gupta',
    'Aarav Shah', 'Kartik Verma', 'Pranav Mishra', 'Tarun Bose', 'Akash Pandey',
    'Harsh Trivedi', 'Yash Dubey', 'Sameer Rao', 'Rajat Sinha', 'Dev Malhotra',
    'Shubham Pillai', 'Ankit Tiwari', 'Gaurav Chauhan', 'Vivek Roy', 'Ritesh Kulkarni',
]

FEMALE_NAMES = [
    'Priya Sharma', 'Sneha Patel', 'Anjali Singh', 'Divya Mehta', 'Pooja Reddy',
    'Riya Nair', 'Kavya Kapoor', 'Simran Joshi', 'Neha Kumar', 'Aisha Khan',
    'Sanya Gupta', 'Tanvi Shah', 'Ishita Verma', 'Kritika Mishra', 'Pallavi Bose',
    'Aditi Pandey', 'Meera Trivedi', 'Shruti Dubey', 'Nandita Rao', 'Swati Sinha',
    'Lavanya Pillai', 'Megha Tiwari', 'Nikita Chauhan', 'Preeti Roy', 'Supriya Kulkarni',
]

DICEBEAR_MALE_STYLES   = ['avataaars', 'micah', 'open-peeps', 'pixel-art']
DICEBEAR_FEMALE_STYLES = ['avataaars', 'micah', 'open-peeps', 'adventurer']


def random_avatar(name: str, gender: str, uid: int) -> str:
    styles = DICEBEAR_MALE_STYLES if gender == 'M' else DICEBEAR_FEMALE_STYLES
    style  = styles[uid % len(styles)]
    seed   = name.replace(' ', '').lower()
    return f'https://api.dicebear.com/8.x/{style}/png?seed={seed}&size=200'


class Command(BaseCommand):
    help = 'Seed 50 demo users with realistic profiles, wallets, and league stats'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=50)
        parser.add_argument('--clear', action='store_true', help='Delete existing seed users first')

    def handle(self, *args, **options):
        count = min(options['count'], 50)

        if options['clear']:
            User.objects.filter(username__startswith='demo_').delete()
            self.stdout.write(self.style.WARNING('Cleared existing demo users.'))

        # Seed default monetization rules
        seed_default_rules()
        self.stdout.write('Seeded monetization rules.')

        all_users_created = []
        half = count // 2
        pairs = [
            (MALE_NAMES[:half],   'M'),
            (FEMALE_NAMES[:half], 'F'),
        ]

        uid = 1
        for name_list, gender in pairs:
            for full_name in name_list:
                username = f"demo_{full_name.replace(' ', '_').lower()}_{uid}"
                if User.objects.filter(username=username).exists():
                    uid += 1
                    continue

                user = User.objects.create_user(
                    username=username,
                    password='Demo@1234',
                    first_name=full_name.split()[0],
                    last_name=full_name.split()[-1],
                )

                avatar_url = random_avatar(full_name, gender, uid)

                Profile.objects.update_or_create(
                    user=user,
                    defaults=dict(
                        phone_number=f'+918{random.randint(100000000, 999999999)}',
                        display_name=full_name,
                        gender=gender,
                        language=random.choice(['ta', 'hi', 'te', 'en', 'ml', 'gu', 'bn']),
                        is_verified=random.choice([True, False]),
                        is_online=random.choice([True, False, False]),
                        bio=f'Hey! I am {full_name.split()[0]}. Love chats and calls. 🎉',
                        age=random.randint(18, 32),
                        location=random.choice(['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Pune', 'Hyderabad']),
                    )
                )

                coins = random.randint(50, 5000)
                money = Decimal(str(round(random.uniform(0, 500), 2)))
                wallet, _ = Wallet.objects.update_or_create(
                    user=user,
                    defaults=dict(
                        coin_balance=coins,
                        money_balance=money if gender == 'F' else Decimal('0.00'),
                        total_earned=coins + random.randint(0, 2000),
                        total_spent=random.randint(0, coins),
                    )
                )

                call_sec  = random.randint(0, 72000)
                calls_rcv = random.randint(0, 200)
                bet_wins  = random.randint(0, 20)
                LeagueStats.objects.update_or_create(
                    user=user,
                    defaults=dict(
                        total_coins_earned=coins + random.randint(0, 1000),
                        total_money_earned=money if gender == 'F' else Decimal('0.00'),
                        total_call_seconds=call_sec,
                        longest_call_seconds=random.randint(0, call_sec // 2 + 1),
                        total_calls_received=calls_rcv,
                        bet_match_wins=bet_wins,
                    )
                )

                all_users_created.append(user)
                self.stdout.write(f'  Created: {full_name} ({gender}) — {username}')
                uid += 1

        # Random follow relationships
        self.stdout.write('Creating follow relationships...')
        for user in all_users_created:
            targets = random.sample(
                [u for u in all_users_created if u != user],
                k=min(random.randint(3, 12), len(all_users_created) - 1)
            )
            for target in targets:
                Follow.objects.get_or_create(follower=user, following=target)

        # Random Call Sessions
        self.stdout.write('Generating random call sessions...')
        # Create a mix of calls where each seeded user participates
        for _ in range(count * 8):
            caller = random.choice(all_users_created)
            callee = random.choice([u for u in all_users_created if u != caller])
            call_type = random.choice(['VOICE', 'VIDEO'])
            # Duration between 1 minute and 3 hours
            duration = random.randint(60, 10800)
            
            # Start time within the last 30 days
            start_time = timezone.now() - timedelta(
                days=random.randint(0, 30), 
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            CallSession.objects.create(
                caller=caller,
                callee=callee,
                call_type=call_type,
                duration_seconds=duration,
                started_at=start_time,
                ended_at=start_time + timedelta(seconds=duration),
                coins_per_min=random.randint(5, 50),
                coins_spent=(duration // 60 + 1) * 10
            )

        self.stdout.write(self.style.SUCCESS(
            f'Done! Created {len(all_users_created)} demo users and hundreds of call sessions.'
        ))
