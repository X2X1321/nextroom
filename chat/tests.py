import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AIIntegration, Message, Room, RoomAIIntegration, UserProfile


class RoomAIAccessTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='pass123')
        self.viewer = User.objects.create_user(username='viewer', password='pass123')
        self.creator_profile = UserProfile.objects.get(user=self.creator)
        AIIntegration.objects.create(profile=self.creator_profile, provider='gpt', api_key='creator-key')
        self.room = Room.objects.create(name='Test Room', slug='test-room', creator=self.creator)

    def test_register_view_rejects_duplicate_username(self):
        User.objects.create_user(username='existing', email='existing@example.com', password='pass123')

        response = self.client.post(
            reverse('register'),
            {
                'username': 'existing',
                'email': 'new@example.com',
                'password': 'newpass123',
                'password_confirm': 'newpass123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='existing').count(), 1)

    def test_register_view_rejects_duplicate_email(self):
        User.objects.create_user(username='taken-name', email='used@example.com', password='pass123')

        response = self.client.post(
            reverse('register'),
            {
                'username': 'new-name',
                'email': 'used@example.com',
                'password': 'newpass123',
                'password_confirm': 'newpass123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='used@example.com').count(), 1)

    def test_landing_page_shows_real_stats(self):
        Room.objects.create(name='Room A', slug='room-a', creator=self.creator)
        Room.objects.create(name='Room B', slug='room-b', creator=self.creator)
        Message.objects.create(room=self.room, user=self.creator, content='hello', created_at=timezone.now())

        response = self.client.get(reverse('landing'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_rooms'], 1)
        self.assertEqual(response.context['online_users'], 0)
        self.assertEqual(response.context['total_messages'], 1)

    def test_creator_can_enable_room_ai_provider_for_other_users(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse('manage_room_ai_integrations', args=[self.room.slug]),
            {'providers': ['gpt']},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(RoomAIIntegration.objects.filter(room=self.room, provider='gpt').exists())

    def test_non_creator_cannot_manage_room_ai_providers(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse('manage_room_ai_integrations', args=[self.room.slug]),
            {'providers': ['gpt']},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RoomAIIntegration.objects.filter(room=self.room, provider='gpt').exists())

    def test_room_member_can_use_room_enabled_agent_without_own_integration(self):
        self.client.force_login(self.creator)
        self.client.post(reverse('manage_room_ai_integrations', args=[self.room.slug]), {'providers': ['gpt']})
        self.client.logout()

        self.client.force_login(self.viewer)
        with patch('chat.views.fetch_ai_response', return_value=('room-agent-response', 10)):
            response = self.client.post(
                reverse('send_message', args=[self.room.slug]),
                data=json.dumps({'content': '@gpt hello there'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.json())
        self.assertTrue(Message.objects.filter(content='room-agent-response').exists())

    def test_room_member_can_use_cloro_gemini_agent(self):
        AIIntegration.objects.create(profile=self.creator_profile, provider='cloro', api_key='cloro-test-key', model_name='gemini')
        self.client.force_login(self.creator)
        self.client.post(reverse('manage_room_ai_integrations', args=[self.room.slug]), {'providers': ['cloro']})
        self.client.logout()

        self.client.force_login(self.viewer)
        with patch('chat.views.fetch_ai_response', return_value=('cloro-gemini-response', 15)):
            response = self.client.post(
                reverse('send_message', args=[self.room.slug]),
                data=json.dumps({'content': '@gemini Explain quantum computing'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.json())
        self.assertTrue(Message.objects.filter(content='cloro-gemini-response').exists())

    def test_guest_can_chat_and_generate_images_and_other_features_require_login(self):
        from .models import GuestSession, GeneratedImage

        # Guest sends a message in room without logging in
        response = self.client.post(
            reverse('send_message', args=[self.room.slug]),
            data=json.dumps({'content': 'Hello from guest!'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(content='Hello from guest!').exists())
        self.assertEqual(GuestSession.objects.count(), 1)
        guest = GuestSession.objects.first()
        self.assertEqual(guest.messages_count, 1)

        # Guest generates an image without logging in
        img_response = self.client.post(
            reverse('generate_image'),
            data=json.dumps({'prompt': 'A neon guest cat'}),
            content_type='application/json',
        )
        self.assertEqual(img_response.status_code, 200)
        self.assertTrue(GeneratedImage.objects.filter(prompt='A neon guest cat').exists())
        guest.refresh_from_db()
        self.assertEqual(guest.images_count, 1)

        # Guest can access dashboard page without 500 error
        dash_res = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_res.status_code, 200)

        # Restricted pages require login and redirect to login page
        profile_res = self.client.get(reverse('profile'))
        self.assertEqual(profile_res.status_code, 302)
        self.assertIn('/login/', profile_res.url)

        ai_res = self.client.get(reverse('ai_management'))
        self.assertEqual(ai_res.status_code, 302)
        self.assertIn('/login/', ai_res.url)

        achieve_res = self.client.get(reverse('achievements'))
        self.assertEqual(achieve_res.status_code, 302)
        self.assertIn('/login/', achieve_res.url)


