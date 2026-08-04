import re
import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import JSONField
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

AI_PROVIDER_CHOICES = [
    ('gpt', 'ChatGPT'),
    ('groq', 'Groq'),
    ('grok', 'Grok'),
    ('deepseek', 'DeepSeek'),
    ('qwen', 'Qwen'),
    ('claude', 'Claude'),
    ('cerebras', 'Cerebras'),
]

SUBSCRIPTION_PLANS = [
    ('free', 'Free'),
    ('premium', 'Premium'),
]

class Room(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'Общее'),
        ('technology', 'Технологии'),
        ('ai', 'ИИ'),
        ('programming', 'Программирование'),
        ('study', 'Учёба'),
        ('science', 'Наука'),
        ('books', 'Книги'),
        ('anime', 'Аниме'),
        ('sport', 'Спорт'),
        ('news', 'Новости'),
        ('humor', 'Юмор'),
        ('creative', 'Творчество'),
        ('design', 'Дизайн'),
        ('business', 'Бизнес'),
        ('startups', 'Стартапы'),
        ('travel', 'Путешествия'),
        ('languages', 'Языки'),
        ('games', 'Игры'),
        ('movies', 'Фильмы'),
        ('music', 'Музыка'),
        ('social', 'Общение'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Room Name")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(max_length=300, blank=True, verbose_name="Description")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    is_private = models.BooleanField(default=False, verbose_name="Private Room")
    access_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Access Code")
    is_pinned = models.BooleanField(default=False, verbose_name="Pinned Room")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'room'
            slug = base_slug
            counter = 2
            while Room.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='free')
    premium_until = models.DateTimeField(null=True, blank=True)
    api_keys = JSONField(default=dict, blank=True)
    visited_rooms = models.ManyToManyField(Room, related_name='visited_by', blank=True)
    custom_prompt = models.TextField(blank=True, help_text='Дополнительные правила для нейросети в чате.')

    def __str__(self):
        return f'{self.user.username} profile'

    @property
    def is_premium(self):
        from django.utils import timezone
        return self.subscription_plan == 'premium' and self.premium_until and self.premium_until >= timezone.now()

    @property
    def room_limit(self):
        return 30 if self.is_premium else 5

    @property
    def invite_limit(self):
        return None if self.is_premium else 10

    @property
    def active_plan(self):
        return 'Premium' if self.is_premium else 'Free'

class AIIntegration(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='integrations')
    provider = models.CharField(max_length=30, choices=AI_PROVIDER_CHOICES)
    api_key = models.CharField(max_length=255)
    model_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('profile', 'provider')

    def __str__(self):
        return f'{self.provider} integration for {self.profile.user.username}'

class RoomAIIntegration(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='ai_integrations')
    provider = models.CharField(max_length=30, choices=AI_PROVIDER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'provider')

    def __str__(self):
        return f'{self.provider} enabled for {self.room.name}'


class RoomInvitation(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invite_code = models.CharField(max_length=16, unique=True)
    invited_username = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = secrets.token_urlsafe(10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Invite {self.invite_code} for {self.room.name}'

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('voice', 'Voice'),
    ]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(verbose_name="Message Content", blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    voice = models.FileField(upload_to='chat_voices/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def get_reactions_summary(self):
        reactions_list = list(self.reactions.all())
        summary = []
        for emoji in ['❤️', '🔥', '😂', '🎉']:
            reactors = [r.user.username for r in reactions_list if r.reaction == emoji]
            summary.append({
                'emoji': emoji,
                'count': len(reactors),
                'reactors': reactors,
            })
        return summary

    def get_image_urls(self):
        if self.image:
            return [self.image.url]
        if not self.content:
            return []
        url_pattern = re.compile(r'(https?://\S+\.(?:jpg|jpeg|png|gif|webp)(?:\?\S*)?)', re.IGNORECASE)
        return url_pattern.findall(self.content)

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]} in {self.room.name}"

class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_reactions')
    reaction = models.CharField(max_length=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'reaction')

    def __str__(self):
        return f"{self.user.username} reacted {self.reaction} to message {self.message.id}"


class Achievement(models.Model):
    CONDITION_TYPES = [
        ('registration', 'Регистрация'),
        ('rooms_created', 'Создано комнат'),
        ('messages', 'Всего сообщений'),
        ('invites', 'Приглашений'),
        ('ai_messages', 'Сообщений к AI'),
        ('consecutive_days', 'Дней подряд'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='lottie-celebration')
    lottie_url = models.URLField(blank=True)
    premium_days = models.IntegerField(default=0)
    condition_type = models.CharField(max_length=30, choices=CONDITION_TYPES)
    condition_value = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"


class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    date = models.DateField()
    messages_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.messages_count} сообщений"


class AIUsageLog(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='ai_usage_logs')
    provider = models.CharField(max_length=30, choices=AI_PROVIDER_CHOICES)
    tokens_used = models.IntegerField(default=0)
    response_time = models.FloatField(default=0.0, help_text='Время ответа в секундах')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.user.username} - {self.provider} - {self.tokens_used} tokens"


class GeneratedImage(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='generated_images')
    prompt = models.TextField()
    image_url = models.TextField()
    generation_time = models.FloatField(null=True, blank=True, help_text='Время генерации в секундах')
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.user.username} - {self.prompt[:50]}"


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        _check_and_grant_achievements(instance, 'registration', 1)


def _check_and_grant_achievements(user, condition_type, condition_value):
    from django.utils import timezone
    if not user or not hasattr(user, 'user_achievements'):
        return []
    earned = []
    achievements = Achievement.objects.filter(condition_type=condition_type, condition_value__lte=condition_value)
    for achievement in achievements:
        if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            UserAchievement.objects.create(user=user, achievement=achievement)
            profile = user.profile
            if achievement.premium_days > 0 and profile:
                from django.utils import timezone
                now = timezone.now()
                if profile.premium_until and profile.premium_until > now:
                    profile.premium_until = profile.premium_until + timezone.timedelta(days=achievement.premium_days)
                else:
                    profile.premium_until = now + timezone.timedelta(days=achievement.premium_days)
                profile.subscription_plan = 'premium'
                profile.save()
            earned.append(achievement)
    return earned


def _ensure_achievements():
    defaults = [
        {'name': 'Новичок', 'description': 'Зарегистрируйтесь в NextRoom', 'icon': 'lottie-celebration', 'premium_days': 10, 'condition_type': 'registration', 'condition_value': 1, 'lottie_url': 'https://lottie.host/efe95c6a-079b-4e5c-8510-e5f279341968/SKYk8dDY60.json'},
        {'name': 'Основатель', 'description': 'Создайте первую комнату', 'icon': 'lottie-star', 'premium_days': 5, 'condition_type': 'rooms_created', 'condition_value': 1, 'lottie_url': 'https://lottie.host/4d65e848-ceb9-412f-8265-3f9250f00e2f/03yolDCrAz.json'},
        {'name': 'Болтун', 'description': 'Напишите 10 сообщений', 'icon': 'lottie-chat', 'premium_days': 2, 'condition_type': 'messages', 'condition_value': 10, 'lottie_url': 'https://lottie.host/1a85d24a-53ce-4884-8bf0-38e4aff1478b/T1gtQIA75C.json'},
        {'name': 'Коммуникатор', 'description': 'Напишите 100 сообщений', 'icon': 'lottie-megaphone', 'premium_days': 5, 'condition_type': 'messages', 'condition_value': 100, 'lottie_url': 'https://lottie.host/1c9c77cc-0e1f-444a-a1ef-a9492494fb1f/tLIspmfYne.json'},
        {'name': 'Гуру чата', 'description': 'Напишите 1000 сообщений', 'icon': 'lottie-crown', 'premium_days': 15, 'condition_type': 'messages', 'condition_value': 1000, 'lottie_url': 'https://lottie.host/d1df02d9-a53f-4c75-9150-ddffcc13b2f6/85r1MVpXy2.json'},
        {'name': 'Командир', 'description': 'Пригласите друзей в комнату', 'icon': 'lottie-rocket', 'premium_days': 10, 'condition_type': 'invites', 'condition_value': 1, 'lottie_url': 'https://lottie.host/b4301e06-63d0-48cd-8024-ee311915f942/4mkLFmOjoy.json'},
        {'name': 'AI-ассистент', 'description': 'Общайтесь с нейросетью', 'icon': 'lottie-robot', 'premium_days': 1, 'condition_type': 'ai_messages', 'condition_value': 1, 'lottie_url': 'https://lottie.host/a325630f-5313-4ee4-841e-ed45f7355f48/X87DTO1KMa.json'},
        {'name': 'Непрерывный', 'description': 'Зайдите в NextRoom 30 дней подряд', 'icon': 'lottie-diamond', 'premium_days': 60, 'condition_type': 'consecutive_days', 'condition_value': 30, 'lottie_url': 'https://lottie.host/33fd2bfb-6be8-4d00-89a5-61dcb569d326/CfQkyKMdgR.json'},
    ]
    seen_names = set()
    for data in defaults:
        if data['name'] in seen_names:
            continue
        seen_names.add(data['name'])
        Achievement.objects.update_or_create(name=data['name'], defaults=data)


@receiver(post_save, sender=Room)
def room_created_check_achievements(sender, instance, created, **kwargs):
    if created and instance.creator_id:
        _check_and_grant_achievements(instance.creator, 'rooms_created', Room.objects.filter(creator_id=instance.creator_id).count())


@receiver(post_save, sender=Message)
def message_created_check_achievements(sender, instance, created, **kwargs):
    if created and instance.user_id:
        user = instance.user
        if not user or not hasattr(user, 'user_achievements'):
            return
        from django.utils import timezone
        today = timezone.now().date()
        activity, _ = UserActivity.objects.get_or_create(user=user, date=today, defaults={'messages_count': 0})
        activity.messages_count += 1
        activity.save()

        total_messages = Message.objects.filter(user=user).count()
        _check_and_grant_achievements(user, 'messages', total_messages)

        if instance.content.strip().startswith('@'):
            _check_and_grant_achievements(user, 'ai_messages', 1)

        streak = _calculate_streak(user)
        if streak >= 30:
            _check_and_grant_achievements(user, 'consecutive_days', streak)


@receiver(post_save, sender=RoomInvitation)
def invitation_created_check_achievements(sender, instance, created, **kwargs):
    if created and instance.invited_by_id:
        invites_count = RoomInvitation.objects.filter(invited_by_id=instance.invited_by_id).count()
        _check_and_grant_achievements(instance.invited_by, 'invites', invites_count)


def _calculate_streak(user):
    activities = UserActivity.objects.filter(user=user).order_by('-date')[:60]
    if not activities:
        return 0
    from django.utils import timezone
    today = timezone.now().date()
    if activities[0].date != today:
        return 0
    streak = 1
    for i in range(len(activities) - 1):
        if (activities[i].date - activities[i + 1].date).days == 1:
            streak += 1
        else:
            break
    return streak
