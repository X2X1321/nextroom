import random
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from chat.models import Room, UserProfile, AIIntegration
from chat.bot_prompts import BOT_NICKNAMES

class Command(BaseCommand):
    help = 'Sets up the AI bot users and distributes them across rooms'

    def handle(self, *args, **kwargs):
        api_key = os.environ.get('OPENROUTER_API_KEY')
        
        self.stdout.write("Creating bot users...")
        bots = []
        for nickname in BOT_NICKNAMES:
            user, created = User.objects.get_or_create(username=nickname)
            if created:
                user.set_unusable_password()
                user.save()
            
            # Profile is automatically created by signal, just update it
            profile = user.profile
            profile.is_bot = True
            profile.save()
            
            # Setup AI Integration
            AIIntegration.objects.update_or_create(
                profile=profile,
                provider='openrouter',
                defaults={
                    'api_key': api_key,
                    'model_name': 'openrouter/auto-beta'
                }
            )
            bots.append(user)
            self.stdout.write(f"  - Bot {nickname} ready.")

        self.stdout.write("Distributing bots across rooms...")
        rooms = list(Room.objects.all())
        
        # Clear existing bot assignments just in case
        for room in rooms:
            room.visited_by.remove(*bots)
            
        for room in rooms:
            # Pick a random number of bots for this room (e.g. 1 to 5)
            # Make sure we don't exceed the number of available bots
            num_bots = random.randint(1, min(5, len(bots)))
            selected_bots = random.sample(bots, num_bots)
            
            for bot in selected_bots:
                bot.profile.visited_rooms.add(room)
            
            self.stdout.write(f"  - Room '{room.name}' now has {num_bots} bots.")

        self.stdout.write(self.style.SUCCESS('Successfully set up AI bots.'))
