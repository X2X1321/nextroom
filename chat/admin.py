from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from .models import Room, Message, UserProfile, AIIntegration, RoomInvitation, GuestSession, GeneratedImage, RouterAIKey

class GrantPremiumByIdForm(forms.Form):
    user_id = forms.IntegerField(label='ID пользователя', min_value=1)

class GrantBalanceByIdForm(forms.Form):
    user_id = forms.IntegerField(label='ID пользователя', min_value=1)
    amount = forms.DecimalField(label='Сумма для добавления (RUB)', max_digits=10, decimal_places=2)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_id', 'subscription_plan', 'premium_until', 'is_premium', 'balance')
    list_filter = ('subscription_plan', 'premium_until')
    search_fields = ('user__username', 'user__email', 'user__id')
    actions = ['grant_premium']
    change_list_template = 'admin/chat/userprofile/change_list.html'

    def user_id(self, obj):
        return obj.user_id

    user_id.short_description = 'ID'

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

    def grant_premium(self, request, queryset):
        updated = 0
        for profile in queryset:
            profile.subscription_plan = 'premium'
            profile.premium_until = timezone.now() + timedelta(days=30)
            profile.save()
            updated += 1
        self.message_user(request, f'Premium выдан {updated} профилям.')

    grant_premium.short_description = 'Выдать Premium выбранным профилям'

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
                    
                    # Sync RouterAI Keys if balance became positive
                    if profile.balance > 0:
                        from chat.views import sync_routerai_keys_state
                        sync_routerai_keys_state(user)

                    messages.success(request, f'Баланс успешно пополнен на {amount} RUB для пользователя {user.username} (ID {user.id}). Текущий баланс: {profile.balance} RUB.')
                    return redirect('admin:chat_userprofile_changelist')
        else:
            form = GrantBalanceByIdForm()

        context = {
            'title': 'Выдать Баланс по ID',
            'opts': self.model._meta,
            'form': form,
        }
        # We use the specific template for granting balance
        return render(request, 'admin/chat/userprofile/grant_balance_by_id.html', context)

admin.site.register(Room)
admin.site.register(Message)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(AIIntegration)
admin.site.register(RoomInvitation)
admin.site.register(GeneratedImage)
admin.site.register(RouterAIKey)


@admin.register(GuestSession)
class GuestSessionAdmin(admin.ModelAdmin):
    list_display = ('guest_name', 'session_key', 'ip_address', 'messages_count', 'images_count', 'first_seen', 'last_activity')
    search_fields = ('guest_name', 'session_key', 'ip_address')
    list_filter = ('first_seen', 'last_activity')
    readonly_fields = ('session_key', 'first_seen', 'last_activity', 'messages_count', 'images_count')

