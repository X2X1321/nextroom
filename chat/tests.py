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

    def test_register_view_rejects_similar_email_alias(self):
        User.objects.create_user(username='gmail-user', email='myname@gmail.com', password='pass123')

        # Try registering with dot or plus alias
        response = self.client.post(
            reverse('register'),
            {
                'username': 'another-user',
                'email': 'm.y.n.a.m.e+spam@gmail.com',
                'password': 'newpass123',
                'password_confirm': 'newpass123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='another-user').count(), 0)


    def test_landing_page_shows_real_stats(self):
        Room.objects.create(name='Room A', slug='room-a', creator=self.creator)
        Room.objects.create(name='Room B', slug='room-b', creator=self.creator)
        Message.objects.create(room=self.room, user=self.creator, content='hello', created_at=timezone.now())

        response = self.client.get(reverse('landing'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_rooms'], 1)
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

    def test_send_image_and_voice_message(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # 1x1 valid transparent GIF
        gif_bytes = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        test_img = SimpleUploadedFile("test.gif", gif_bytes, content_type="image/gif")
        test_voice = SimpleUploadedFile("voice.webm", b"fake_voice_bytes", content_type="audio/webm")

        img_res = self.client.post(
            reverse('send_message', args=[self.room.slug]),
            {'image': test_img, 'content': ''}
        )
        self.assertEqual(img_res.status_code, 200)
        self.assertTrue(Message.objects.filter(message_type='image').exists())

        voice_res = self.client.post(
            reverse('send_message', args=[self.room.slug]),
            {'voice': test_voice, 'content': ''}
        )
        self.assertEqual(voice_res.status_code, 200)
        self.assertTrue(Message.objects.filter(message_type='voice').exists())

    def test_cache_utils_get_and_set(self):
        from .cache_utils import get_cache, set_cache
        self.assertTrue(set_cache('test_key_abc', {'data': 123}, timeout=30))
        cached = get_cache('test_key_abc')
        self.assertIsNotNone(cached)
        self.assertEqual(cached.get('data'), 123)

    def test_confirm_subscription_idempotency(self):
        from .models import Payment
        self.client.force_login(self.creator)
        
        mock_payment_data = {
            'id': 'pay_test_123',
            'status': 'succeeded',
            'metadata': {'user_id': str(self.creator.id)}
        }
        with patch('chat.views.yookassa_request', return_value=mock_payment_data):
            # First confirmation
            res1 = self.client.get(reverse('subscription_confirm') + '?paymentId=pay_test_123')
            self.assertEqual(res1.status_code, 302)
            payment = Payment.objects.get(payment_id='pay_test_123')
            self.assertEqual(payment.status, 'succeeded')
            self.creator_profile.refresh_from_db()
            expiry1 = self.creator_profile.premium_until

            # Second confirmation (replay attack / refresh)
            res2 = self.client.get(reverse('subscription_confirm') + '?paymentId=pay_test_123')
            self.assertEqual(res2.status_code, 302)
            self.creator_profile.refresh_from_db()
            # Expiry date must not be extended again
            self.assertEqual(self.creator_profile.premium_until, expiry1)

    def test_profile_avatar_upload(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.creator)
        
        # Create a test image
        img = Image.new('RGB', (600, 400), color=(73, 109, 137))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        uploaded_file = SimpleUploadedFile('test_avatar.jpg', img_bytes.getvalue(), content_type='image/jpeg')

        response = self.client.post(
            reverse('profile'),
            {'avatar': uploaded_file},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'ok')
        self.creator_profile.refresh_from_db()
        self.assertTrue(self.creator_profile.avatar_url is not None and len(self.creator_profile.avatar_url) > 0)
