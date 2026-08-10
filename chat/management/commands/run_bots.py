import time
import random
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from chat.models import Room, Message, User, UserProfile, MovieGame
from chat.bot_prompts import get_bot_prompt, get_movie_game_start_message
from chat.views import fetch_chat_completion, MOVIE_DB, get_ai_bot_user

class Command(BaseCommand):
    help = 'Runs the bot simulation worker'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Bot Simulation Worker...")
        last_movie_game_time = timezone.now() - timedelta(minutes=10) # Start first game in 5 mins

        while True:
            now = timezone.now()
            
            # Find all bots
            bots = User.objects.filter(profile__is_bot=True)
            if not bots.exists():
                self.stdout.write("No bots found. Please run 'python manage.py setup_bots' first. Waiting...")
                time.sleep(30)
                continue

            rooms = Room.objects.all()

            for room in rooms:
                # Bots in this room
                room_bots = list(bots.filter(profile__visited_rooms=room))
                if not room_bots:
                    continue

                # Get recent messages
                recent_messages = list(Message.objects.filter(room=room).order_by('-created_at')[:15])
                recent_messages.reverse()

                if recent_messages:
                    last_msg = recent_messages[-1]
                    
                    # If last message was within the last 30 seconds
                    time_since_last = (now - last_msg.created_at).total_seconds()
                    
                    if time_since_last <= 30:
                        is_last_human = not (last_msg.user and getattr(last_msg.user, 'profile', None) and last_msg.user.profile.is_bot)
                        
                        # Probabilistically reply to human or other bots
                        # 40% chance to reply if human, 15% chance if bot
                        chance = 0.4 if is_last_human else 0.15
                        
                        if random.random() < chance:
                            speaking_bot = random.choice(room_bots)
                            
                            # Build context
                            context_str = "\n".join([
                                f"{m.user.username if m.user else (m.guest_name or 'Гость')}: {m.content}" 
                                for m in recent_messages
                            ])
                            
                            prompt = f"Контекст последних сообщений:\n{context_str}\n\nНапиши короткий естественный ответ или реплику в продолжение разговора от лица обычного пользователя."
                            
                            integration = speaking_bot.profile.integrations.filter(provider='openrouter').first()
                            if integration:
                                try:
                                    system_prompt = get_bot_prompt(speaking_bot.username, room.name)
                                    response = fetch_chat_completion(
                                        provider='openrouter',
                                        prompt=prompt,
                                        api_key=integration.api_key,
                                        model=integration.model_name or 'openrouter/auto-beta',
                                        custom_prompt=system_prompt
                                    )
                                    
                                    if response and response.strip():
                                        Message.objects.create(
                                            room=room,
                                            user=speaking_bot,
                                            content=response,
                                            message_type='text'
                                        )
                                        self.stdout.write(f"[{timezone.now()}] Bot {speaking_bot.username} replied in {room.name}.")
                                except Exception as e:
                                    self.stdout.write(f"Bot error: {e}")

            # Check if we should start "Угадай фильм"
            if (now - last_movie_game_time).total_seconds() > 900:  # 15 minutes
                # Pick a random room with bots and a random bot
                active_rooms = Room.objects.filter(visited_by__is_bot=True).distinct()
                if active_rooms.exists():
                    room = random.choice(active_rooms)
                    room_bots = list(bots.filter(profile__visited_rooms=room))
                    if room_bots:
                        bot = random.choice(room_bots)
                        
                        # Create movie game
                        active_game = MovieGame.objects.filter(room=room, is_active=True).first()
                        if not active_game:
                            movie_data = random.choice(MOVIE_DB)
                            game = MovieGame.objects.create(
                                room=room,
                                started_by=bot,
                                movie_name=movie_data['title'],
                                hints=movie_data['hints']
                            )
                            # Bot user message asking to play
                            Message.objects.create(
                                room=room,
                                user=bot,
                                content=get_movie_game_start_message(),
                                message_type='text'
                            )
                            # System message starting the game
                            sys_bot = get_ai_bot_user()
                            first_hint = game.hints[0]
                            bot_message = f"Я загадал фильм.\n\nПодсказка №1:\n{first_hint}\n\nУ вас есть 10 попыток."
                            Message.objects.create(room=room, user=sys_bot, content=bot_message, message_type='text')

                            last_movie_game_time = now
                            self.stdout.write(f"[{timezone.now()}] Bot {bot.username} started Movie Game in {room.name}.")
            
            # Check for movie game guessing
            active_games = MovieGame.objects.filter(is_active=True)
            for game in active_games:
                room_bots = list(bots.filter(profile__visited_rooms=game.room))
                if room_bots:
                    # 15% chance per tick to try guessing
                    if random.random() < 0.15:
                        bot = random.choice(room_bots)
                        hints_str = ", ".join(game.hints[:game.current_hint_index + 1])
                        prompt = f"В комнате идет игра 'Угадай фильм'. Известные подсказки: {hints_str}. Попытайся угадать название фильма на русском языке (напиши только название или короткую фразу). Не используй кавычки."
                        
                        integration = bot.profile.integrations.filter(provider='openrouter').first()
                        if integration:
                            try:
                                system_prompt = get_bot_prompt(bot.username, game.room.name)
                                response = fetch_chat_completion(
                                    provider='openrouter',
                                    prompt=prompt,
                                    api_key=integration.api_key,
                                    model=integration.model_name or 'openrouter/auto-beta',
                                    custom_prompt=system_prompt
                                )
                                if response and response.strip():
                                    Message.objects.create(
                                        room=game.room,
                                        user=bot,
                                        content=response,
                                        message_type='text'
                                    )
                                    self.stdout.write(f"[{timezone.now()}] Bot {bot.username} guessed movie in {game.room.name}.")
                            except Exception:
                                pass

            time.sleep(15)
