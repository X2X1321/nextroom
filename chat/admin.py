from datetime import timedelta
import logging

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Achievement,
    AIIntegration,
    AIUsageLog,
    GeneratedImage,
    GuestSession,
    Message,
    MessageReaction,
    MovieGame,
    Payment,
    Room,
    RoomAIIntegration,
    RoomInvitation,
    RouterAIKey,
    UserAchievement,
    UserActivity,
    UserProfile,
)

logger = logging.getLogger(__name__)

# Admin Site Titles
admin.site.site_header = 'NextRoom Control Center'
admin.site.site_title = 'NextRoom Admin'
admin.site.index_title = 'Панель управления платформой'


class GrantPremiumByIdForm(forms.Form):
    user_id = forms.IntegerField(label='ID пользователя', min_value=1)


class GrantBalanceByIdForm(forms.Form):
    user_id = forms.IntegerField(label='ID пользователя', min_value=1)
    amount = forms.DecimalField(label='Сумма для добавления (RUB)', max_digits=10, decimal_places=2)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'avatar_preview',
        'user_link',
        'user_id',
        'plan_badge',
        'balance_badge',
        'premium_until_display',
        'rooms_created_count',
    )
    list_filter = ('subscription_plan', 'is_bot')
    search_fields = ('user__username', 'user__email', 'user__id')
    list_select_related = ('user',)
    list_per_page = 25
    actions = ['grant_premium_30d', 'grant_100_rub', 'reset_balance']
    change_list_template = 'admin/chat/userprofile/change_list.html'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            rooms_count=Count('user__created_rooms', distinct=True)
        )

    def avatar_preview(self, obj):
        if obj.avatar_url:
            return format_html(
                '<img src="{}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid #334155;" />',
                obj.avatar_url
            )
        initial = (obj.user.username[0] if obj.user and obj.user.username else '?').upper()
        return format_html(
            '<div style="width: 32px; height: 32px; border-radius: 50%; background: #312e81; color: #818cf8; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px;">{}</div>',
            initial
        )
    avatar_preview.short_description = 'Фото'

    def user_link(self, obj):
        if not obj.user:
            return '-'
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}" style="font-weight: 600; color: #818cf8;">{}</a>',
            url,
            obj.user.username
        )
    user_link.short_description = 'Пользователь'
    user_link.admin_order_field = 'user__username'

    def user_id(self, obj):
        return obj.user_id
    user_id.short_description = 'ID'
    user_id.admin_order_field = 'user__id'

    def plan_badge(self, obj):
        if obj.subscription_plan == 'premium' and obj.is_premium:
            return format_html(
                '<span style="background: linear-gradient(135deg, #6366f1, #a855f7); color: #fff; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">PREMIUM</span>'
            )
        return format_html(
            '<span style="background: #1e293b; color: #94a3b8; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;">FREE</span>'
        )
    plan_badge.short_description = 'Тариф'
    plan_badge.admin_order_field = 'subscription_plan'

    def balance_badge(self, obj):
        color = '#10b981' if obj.balance > 0 else '#94a3b8'
        return format_html(
            '<span style="font-weight: 700; color: {};">{} ₽</span>',
            color,
            obj.balance
        )
    balance_badge.short_description = 'Баланс'
    balance_badge.admin_order_field = 'balance'

    def premium_until_display(self, obj):
        if not obj.premium_until:
            return '-'
        is_active = obj.is_premium
        color = '#a855f7' if is_active else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: 500;">{}</span>',
            color,
            obj.premium_until.strftime('%d.%m.%Y %H:%M')
        )
    premium_until_display.short_description = 'Premium до'
    premium_until_display.admin_order_field = 'premium_until'

    def rooms_created_count(self, obj):
        return getattr(obj, 'rooms_count', 0)
    rooms_created_count.short_description = 'Комнат'
    rooms_created_count.admin_order_field = 'rooms_count'

    def grant_premium_30d(self, request, queryset):
        count = 0
        for p in queryset:
            p.subscription_plan = 'premium'
            p.premium_until = timezone.now() + timedelta(days=30)
            p.save()
            count += 1
        self.message_user(request, f'Premium на 30 дней успешно выдан {count} пользователям.')
    grant_premium_30d.short_description = '✨ Выдать Premium на 30 дней'

    def grant_100_rub(self, request, queryset):
        count = 0
        for p in queryset:
            p.balance += 100
            p.save()
            count += 1
        self.message_user(request, f'Начислено 100 ₽ для {count} пользователей.')
    grant_100_rub.short_description = '💰 Пополнить баланс на 100 ₽'

    def reset_balance(self, request, queryset):
        updated = queryset.update(balance=0)
        self.message_user(request, f'Баланс обнулен у {updated} пользователей.')
    reset_balance.short_description = '⚠️ Обнулить баланс'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'grant-premium-by-id/',
                self.admin_site.admin_view(self.grant_premium_by_id_view),
                name='chat_userprofile_grant_premium_by_id',
            ),
            path(
                'grant-balance-by-id/',
                self.admin_site.admin_view(self.grant_balance_by_id_view),
                name='chat_userprofile_grant_balance_by_id',
            ),
        ]
        return custom_urls + urls

    def grant_premium_by_id_view(self, request):
        if request.method == 'POST':
            form = GrantPremiumByIdForm(request.POST)
            if form.is_valid():
                user_id = form.cleaned_data['user_id']
                try:
                    user = User.objects.get(pk=user_id)
                except User.DoesNotExist:
                    messages.error(request, 'Пользователь с таким ID не найден.')
                else:
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.subscription_plan = 'premium'
                    profile.premium_until = timezone.now() + timedelta(days=30)
                    profile.save()
                    messages.success(request, f'Premium успешно выдан пользователю {user.username} (ID {user.id}).')
                    return redirect('admin:chat_userprofile_changelist')
        else:
            form = GrantPremiumByIdForm()

        context = {
            'title': 'Выдать Premium по ID',
            'opts': self.model._meta,
            'form': form,
        }
        return render(request, 'admin/chat/userprofile/grant_premium_by_id.html', context)

    def grant_balance_by_id_view(self, request):
        if request.method == 'POST':
            form = GrantBalanceByIdForm(request.POST)
            if form.is_valid():
                user_id = form.cleaned_data['user_id']
                amount = form.cleaned_data['amount']
                try:
                    user = User.objects.get(pk=user_id)
                except User.DoesNotExist:
                    messages.error(request, 'Пользователь с таким ID не найден.')
                else:
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.balance += amount
                    profile.save()
                    if profile.balance > 0:
                        from chat.views import sync_routerai_keys_state
                        sync_routerai_keys_state(user)

                    messages.success(request, f'Баланс успешно пополнен на {amount} RUB для {user.username}. Итого: {profile.balance} RUB.')
                    return redirect('admin:chat_userprofile_changelist')
        else:
            form = GrantBalanceByIdForm()

        context = {
            'title': 'Выдать Баланс по ID',
            'opts': self.model._meta,
            'form': form,
        }
        return render(request, 'admin/chat/userprofile/grant_balance_by_id.html', context)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'creator_link',
        'category_badge',
        'status_badges',
        'messages_count_display',
        'created_at',
    )
    list_filter = ('category', 'is_private', 'is_pinned', 'created_at')
    search_fields = ('name', 'slug', 'description', 'creator__username')
    list_select_related = ('creator', 'creator__profile')
    list_per_page = 25
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['creator']
    actions = ['make_pinned', 'make_unpinned', 'make_public', 'make_private']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            msg_count=Count('messages')
        )

    def creator_link(self, obj):
        if not obj.creator:
            return '-'
        url = reverse('admin:auth_user_change', args=[obj.creator.id])
        return format_html(
            '<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>',
            url,
            obj.creator.username
        )
    creator_link.short_description = 'Создатель'
    creator_link.admin_order_field = 'creator__username'

    def category_badge(self, obj):
        return format_html(
            '<span style="background: #1e293b; color: #cbd5e1; padding: 2px 8px; border-radius: 6px; font-size: 11px;">{}</span>',
            obj.get_category_display()
        )
    category_badge.short_description = 'Категория'
    category_badge.admin_order_field = 'category'

    def status_badges(self, obj):
        badges = []
        if obj.is_pinned:
            badges.append('<span style="background: #eab308; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">📌 ЗАКРЕП</span>')
        if obj.is_private:
            badges.append('<span style="background: #dc2626; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">🔒 ЗАКРЫТАЯ</span>')
        else:
            badges.append('<span style="background: #059669; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">🌐 ОТКРЫТАЯ</span>')
        return mark_safe(' '.join(badges))
    status_badges.short_description = 'Статус'

    def messages_count_display(self, obj):
        count = getattr(obj, 'msg_count', 0)
        return format_html(
            '<span style="color: #60a5fa; font-weight: 700;">{}</span>',
            count
        )
    messages_count_display.short_description = 'Сообщений'
    messages_count_display.admin_order_field = 'msg_count'

    def make_pinned(self, request, queryset):
        updated = queryset.update(is_pinned=True)
        self.message_user(request, f'{updated} комнат(ы) закреплены.')
    make_pinned.short_description = '📌 Закрепить выбранные комнаты'

    def make_unpinned(self, request, queryset):
        updated = queryset.update(is_pinned=False)
        self.message_user(request, f'Снято закрепление с {updated} комнат.')
    make_unpinned.short_description = 'Открепить выбранные комнаты'

    def make_public(self, request, queryset):
        updated = queryset.update(is_private=False)
        self.message_user(request, f'{updated} комнат сделаны открытыми.')
    make_public.short_description = '🌐 Сделать открытыми'

    def make_private(self, request, queryset):
        updated = queryset.update(is_private=True)
        self.message_user(request, f'{updated} комнат сделаны приватными.')
    make_private.short_description = '🔒 Сделать приватными'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sender_display',
        'room_link',
        'type_badge',
        'content_snippet',
        'media_preview',
        'created_at',
    )
    list_filter = ('message_type', 'created_at')
    search_fields = ('content', 'user__username', 'guest_name', 'room__name')
    list_select_related = ('room', 'user', 'guest_session', 'reply_to')
    raw_id_fields = ('room', 'user', 'guest_session', 'reply_to')
    date_hierarchy = 'created_at'
    list_per_page = 30
    show_full_result_count = False

    def sender_display(self, obj):
        if obj.user:
            return format_html(
                '<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>',
                reverse('admin:auth_user_change', args=[obj.user.id]),
                obj.user.username
            )
        return format_html(
            '<span style="color: #94a3b8; font-style: italic;">Гость: {}</span>',
            obj.guest_name or 'Аноним'
        )
    sender_display.short_description = 'Отправитель'
    sender_display.admin_order_field = 'user__username'

    def room_link(self, obj):
        if not obj.room:
            return '-'
        url = reverse('admin:chat_room_change', args=[obj.room.id])
        return format_html(
            '<a href="{}" style="color: #38bdf8;">{}</a>',
            url,
            obj.room.name
        )
    room_link.short_description = 'Комната'
    room_link.admin_order_field = 'room__name'

    def type_badge(self, obj):
        types = {
            'text': ('#3b82f6', '💬 Текст'),
            'image': ('#8b5cf6', '🖼️ Фото'),
            'voice': ('#10b981', '🎙️ Голос'),
        }
        color, label = types.get(obj.message_type, ('#6b7280', obj.message_type))
        return format_html(
            '<span style="background: rgba(255,255,255,0.06); border: 1px solid {}; color: {}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">{}</span>',
            color, color, label
        )
    type_badge.short_description = 'Тип'
    type_badge.admin_order_field = 'message_type'

    def content_snippet(self, obj):
        if not obj.content:
            return '-'
        snippet = obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return format_html('<span style="color: #e2e8f0;">{}</span>', snippet)
    content_snippet.short_description = 'Содержание'

    def media_preview(self, obj):
        previews = []
        if obj.image:
            previews.append(format_html(
                '<a href="{}" target="_blank"><img src="{}" style="width: 32px; height: 32px; border-radius: 4px; object-fit: cover;" /></a>',
                obj.image.url, obj.image.url
            ))
        if obj.voice:
            previews.append(format_html(
                '<a href="{}" target="_blank" style="color: #10b981; font-size: 11px;">▶ Аудио</a>',
                obj.voice.url
            ))
        return mark_safe(' '.join(previews)) if previews else '-'
    media_preview.short_description = 'Медиа'


@admin.register(AIIntegration)
class AIIntegrationAdmin(admin.ModelAdmin):
    list_display = ('profile_link', 'provider_badge', 'nickname', 'auto_reply', 'created_at')
    list_filter = ('provider', 'auto_reply', 'created_at')
    search_fields = ('profile__user__username', 'provider', 'nickname')
    list_select_related = ('profile', 'profile__user')
    list_per_page = 25

    def profile_link(self, obj):
        if not obj.profile or not obj.profile.user:
            return '-'
        url = reverse('admin:chat_userprofile_change', args=[obj.profile.id])
        return format_html('<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>', url, obj.profile.user.username)
    profile_link.short_description = 'Профиль'

    def provider_badge(self, obj):
        return format_html(
            '<span style="background: #312e81; color: #a5b4fc; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            obj.get_provider_display()
        )
    provider_badge.short_description = 'Провайдер'


@admin.register(RoomAIIntegration)
class RoomAIIntegrationAdmin(admin.ModelAdmin):
    list_display = ('room_link', 'provider_badge', 'created_at')
    list_filter = ('provider', 'created_at')
    search_fields = ('room__name', 'provider')
    list_select_related = ('room',)
    list_per_page = 25

    def room_link(self, obj):
        if not obj.room:
            return '-'
        url = reverse('admin:chat_room_change', args=[obj.room.id])
        return format_html('<a href="{}" style="color: #38bdf8;">{}</a>', url, obj.room.name)
    room_link.short_description = 'Комната'

    def provider_badge(self, obj):
        return format_html(
            '<span style="background: #1e1b4b; color: #c7d2fe; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            obj.provider.upper()
        )
    provider_badge.short_description = 'Провайдер'


@admin.register(GeneratedImage)
class GeneratedImageAdmin(admin.ModelAdmin):
    list_display = (
        'image_thumbnail',
        'creator_display',
        'model_badge',
        'prompt_snippet',
        'generation_time_display',
        'created_at',
    )
    list_filter = ('model_name', 'created_at')
    search_fields = ('prompt', 'model_name', 'profile__user__username')
    list_select_related = ('profile', 'profile__user', 'guest_session')
    list_per_page = 25
    show_full_result_count = False

    def image_thumbnail(self, obj):
        if obj.image_url:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="width: 44px; height: 44px; border-radius: 6px; object-fit: cover; border: 1px solid #334155;" /></a>',
                obj.image_url,
                obj.image_url
            )
        return '-'
    image_thumbnail.short_description = 'Превью'

    def creator_display(self, obj):
        if obj.profile and obj.profile.user:
            return format_html(
                '<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>',
                reverse('admin:auth_user_change', args=[obj.profile.user.id]),
                obj.profile.user.username
            )
        if obj.guest_session:
            return format_html('<span style="color: #94a3b8; font-style: italic;">Гость: {}</span>', obj.guest_session.guest_name)
        return '-'
    creator_display.short_description = 'Автор'

    def model_badge(self, obj):
        return format_html(
            '<span style="background: #1e293b; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            obj.model_name or 'Auto'
        )
    model_badge.short_description = 'Модель'

    def prompt_snippet(self, obj):
        prompt = obj.prompt or ''
        return prompt[:70] + '...' if len(prompt) > 70 else prompt
    prompt_snippet.short_description = 'Промпт'

    def generation_time_display(self, obj):
        return f"{obj.generation_time:.2f} сек" if obj.generation_time else '-'
    generation_time_display.short_description = 'Время'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'user_link', 'amount_display', 'status_badge', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('payment_id', 'user__username', 'user__email')
    list_select_related = ('user',)
    list_per_page = 25

    def user_link(self, obj):
        if not obj.user:
            return '-'
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>', url, obj.user.username)
    user_link.short_description = 'Пользователь'

    def amount_display(self, obj):
        return format_html('<span style="font-weight: 700; color: #10b981;">{} ₽</span>', obj.amount)
    amount_display.short_description = 'Сумма'

    def status_badge(self, obj):
        colors = {
            'succeeded': ('#059669', 'УСПЕШНО'),
            'pending': ('#eab308', 'ОЖИДАНИЕ'),
            'canceled': ('#dc2626', 'ОТМЕНЕНО'),
        }
        bg, text = colors.get(obj.status, ('#6b7280', obj.status.upper()))
        return format_html(
            '<span style="background: {}; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">{}</span>',
            bg, text
        )
    status_badge.short_description = 'Статус'


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ('user_display', 'provider_badge', 'tokens_used', 'response_time_display', 'created_at')
    list_filter = ('provider', 'created_at')
    search_fields = ('profile__user__username', 'provider')
    list_select_related = ('profile', 'profile__user')
    list_per_page = 30
    show_full_result_count = False

    def user_display(self, obj):
        if obj.profile and obj.profile.user:
            return obj.profile.user.username
        return '-'
    user_display.short_description = 'Пользователь'

    def provider_badge(self, obj):
        return format_html(
            '<span style="background: #1e293b; color: #a5b4fc; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            obj.provider.upper()
        )
    provider_badge.short_description = 'Провайдер'

    def response_time_display(self, obj):
        return f"{obj.response_time:.2f} сек" if obj.response_time else '-'
    response_time_display.short_description = 'Отклик'


@admin.register(GuestSession)
class GuestSessionAdmin(admin.ModelAdmin):
    list_display = (
        'guest_name',
        'session_key',
        'ip_address',
        'messages_count',
        'images_count',
        'first_seen',
        'last_activity',
    )
    search_fields = ('guest_name', 'session_key', 'ip_address')
    list_filter = ('first_seen', 'last_activity')
    readonly_fields = ('session_key', 'first_seen', 'last_activity', 'messages_count', 'images_count')
    list_per_page = 25
    show_full_result_count = False


@admin.register(RouterAIKey)
class RouterAIKeyAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'name', 'key_preview', 'is_disabled_badge', 'created_at')
    list_filter = ('is_disabled', 'created_at')
    search_fields = ('user__username', 'name', 'key_value')
    list_select_related = ('user',)

    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}" style="color: #818cf8; font-weight: 600;">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'Пользователь'

    def key_preview(self, obj):
        if not obj.key_value:
            return '-'
        return f"{obj.key_value[:8]}...{obj.key_value[-4:]}"
    key_preview.short_description = 'Ключ'

    def is_disabled_badge(self, obj):
        if obj.is_disabled:
            return format_html('<span style="color: #ef4444; font-weight: 700;">ОТКЛЮЧЕН</span>')
        return format_html('<span style="color: #10b981; font-weight: 700;">АКТИВЕН</span>')
    is_disabled_badge.short_description = 'Статус'


@admin.register(RoomInvitation)
class RoomInvitationAdmin(admin.ModelAdmin):
    list_display = ('invite_code', 'room', 'invited_by', 'invited_username', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('invite_code', 'room__name', 'invited_by__username', 'invited_username')
    list_select_related = ('room', 'invited_by')
    list_per_page = 25


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'condition_type', 'condition_value', 'premium_days')
    list_filter = ('condition_type',)
    search_fields = ('name', 'description')


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'earned_at')
    list_filter = ('earned_at', 'achievement')
    search_fields = ('user__username', 'achievement__name')
    list_select_related = ('user', 'achievement')


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'messages_count')
    list_filter = ('date',)
    search_fields = ('user__username',)
    list_select_related = ('user',)
    list_per_page = 30


@admin.register(MovieGame)
class MovieGameAdmin(admin.ModelAdmin):
    list_display = ('room', 'movie_name', 'is_active', 'total_attempts', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('room__name', 'movie_name')
    list_select_related = ('room',)


