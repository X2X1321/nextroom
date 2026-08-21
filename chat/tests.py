import json
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    AIIntegration, Message, Room, RoomAIIntegration,
    UserProfile, MessageReaction, Achievement, UserAchievement,
    RoomInvitation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, password="pass1234", email=""):
    return User.objects.create_user(username=username, password=password, email=email)


# ===========================================================================
# Registration Tests
# ===========================================================================

class RegistrationTests(TestCase):
    """Tests for register_view: validation, captcha, duplicates."""

    def _post_register(self, username, password, confirm=None, email="", token="ok-token"):
        return self.client.post(
            reverse("register"),
            {
                "username": username,
                "email": email,
                "password": password,
                "password_confirm": confirm or password,
                "smart-token": token,
            },
        )

    @override_settings(SMARTCAPTCHA_SERVER_KEY="test-server-key")
    def test_register_blocked_when_captcha_fails(self):
        with patch("chat.views._verify_smartcaptcha", return_value=False):
            response = self._post_register("newuser", "pass1234")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_register_success_redirects_to_dashboard(self):
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register("freshuser", "pass1234")
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="freshuser").exists())

    def test_register_rejects_duplicate_username(self):
        make_user("existing")
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register("existing", "pass1234", email="new@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="existing").count(), 1)

    def test_register_rejects_duplicate_email(self):
        make_user("taken-name", email="used@example.com")
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register("new-name", "pass1234", email="used@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="used@example.com").count(), 1)

    def test_register_rejects_gmail_dot_alias(self):
        make_user("gmail-user", email="myname@gmail.com")
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register(
                "another-user", "pass1234", email="m.y.n.a.m.e+spam@gmail.com"
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="another-user").exists())

    def test_register_rejects_password_mismatch(self):
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register("mismatch", "pass1234", confirm="different")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_register_rejects_short_password(self):
        with patch("chat.views._verify_smartcaptcha", return_value=True):
            response = self._post_register("shortpass", "abc")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="shortpass").exists())

    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_from_register(self):
        u = make_user("alreadyin")
        self.client.force_login(u)
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)


# ===========================================================================
# Authentication Tests
# ===========================================================================

class AuthTests(TestCase):

    def setUp(self):
        self.user = make_user("loginuser", password="loginpass")

    def test_login_success(self):
        response = self.client.post(
            reverse("login"), {"username": "loginuser", "password": "loginpass"}
        )
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse("login"), {"username": "loginuser", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, 200)

    def test_logout_redirects_to_landing(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("landing"), fetch_redirect_response=False)

    def test_authenticated_user_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)


# ===========================================================================
# Room Tests
# ===========================================================================

class RoomTests(TestCase):

    def setUp(self):
        self.creator = make_user("creator")
        self.other = make_user("other")
        self.room = Room.objects.create(
            name="Test Room", slug="test-room", creator=self.creator
        )

    def test_create_room_requires_login(self):
        response = self.client.post(reverse("create_room"), {"name": "New Room"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_create_room_success(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("create_room"),
            {"name": "My New Room", "description": "desc", "category": "general"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Room.objects.filter(name="My New Room").exists())

    def test_delete_room_by_creator(self):
        self.client.force_login(self.creator)
        self.client.post(reverse("delete_room", args=[self.room.slug]), follow=True)
        self.assertFalse(Room.objects.filter(slug="test-room").exists())

    def test_delete_room_by_non_creator_forbidden(self):
        self.client.force_login(self.other)
        self.client.post(reverse("delete_room", args=[self.room.slug]))
        self.assertTrue(Room.objects.filter(slug="test-room").exists())

    def test_room_detail_accessible(self):
        response = self.client.get(reverse("room_detail", args=[self.room.slug]))
        self.assertEqual(response.status_code, 200)

    def test_private_room_shows_unlock_form(self):
        private = Room.objects.create(
            name="Private", slug="private-room", creator=self.creator,
            is_private=True, access_code="secret123"
        )
        response = self.client.get(reverse("room_detail", args=[private.slug]))
        self.assertTemplateUsed(response, "chat/room_unlock.html")

    def test_private_room_unlocked_with_correct_code(self):
        private = Room.objects.create(
            name="Private2", slug="private2", creator=self.creator,
            is_private=True, access_code="mycode"
        )
        response = self.client.post(
            reverse("room_detail", args=[private.slug]),
            {"access_code": "mycode"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/room_detail.html")

    def test_private_room_not_unlocked_with_wrong_code(self):
        private = Room.objects.create(
            name="Private3", slug="private3", creator=self.creator,
            is_private=True, access_code="correct"
        )
        response = self.client.post(
            reverse("room_detail", args=[private.slug]),
            {"access_code": "wrong"},
        )
        self.assertTemplateUsed(response, "chat/room_unlock.html")

    def test_pin_toggle_by_creator(self):
        self.client.force_login(self.creator)
        self.assertFalse(self.room.is_pinned)
        self.client.post(reverse("toggle_room_pin", args=[self.room.slug]))
        self.room.refresh_from_db()
        self.assertTrue(self.room.is_pinned)


# ===========================================================================
# Messaging Tests
# ===========================================================================

class MessagingTests(TestCase):

    def setUp(self):
        self.creator = make_user("msgcreator")
        self.viewer = make_user("msgviewer")
        self.room = Room.objects.create(
            name="Msg Room", slug="msg-room", creator=self.creator
        )

    def _send(self, content, user=None):
        if user:
            self.client.force_login(user)
        return self.client.post(
            reverse("send_message", args=[self.room.slug]),
            data=json.dumps({"content": content}),
            content_type="application/json",
        )

    def test_send_text_message_authenticated(self):
        response = self._send("Hello world!", user=self.creator)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(Message.objects.filter(content="Hello world!", room=self.room).exists())

    def test_send_text_message_guest(self):
        response = self._send("Guest message")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(Message.objects.filter(content="Guest message").exists())

    def test_send_empty_message_rejected(self):
        response = self._send("", user=self.creator)
        self.assertEqual(response.status_code, 400)

    def test_send_message_method_not_allowed(self):
        self.client.force_login(self.creator)
        response = self.client.get(reverse("send_message", args=[self.room.slug]))
        self.assertEqual(response.status_code, 405)

    def test_send_image_message(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        gif = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
            b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
            b"\x00\x00\x02\x02D\x01\x00;"
        )
        self.client.force_login(self.creator)
        img = SimpleUploadedFile("test.gif", gif, content_type="image/gif")
        response = self.client.post(
            reverse("send_message", args=[self.room.slug]),
            {"image": img, "content": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(message_type="image", room=self.room).exists())

    def test_send_voice_message(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.creator)
        voice = SimpleUploadedFile("voice.webm", b"fakeaudio", content_type="audio/webm")
        response = self.client.post(
            reverse("send_message", args=[self.room.slug]),
            {"voice": voice, "content": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(message_type="voice", room=self.room).exists())

    def test_send_to_private_room_unauthorized(self):
        private = Room.objects.create(
            name="PrivateMsg", slug="private-msg", creator=self.creator,
            is_private=True, access_code="secret"
        )
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("send_message", args=[private.slug]),
            data=json.dumps({"content": "unauthorized"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


# ===========================================================================
# get_messages Endpoint Tests
# ===========================================================================

class GetMessagesTests(TestCase):

    def setUp(self):
        self.creator = make_user("pollcreator")
        self.room = Room.objects.create(
            name="Poll Room", slug="poll-room", creator=self.creator
        )
        for i in range(60):
            Message.objects.create(
                room=self.room, user=self.creator, content=f"msg {i}"
            )

    def _get(self, after_id=None):
        url = reverse("get_messages", args=[self.room.slug])
        if after_id is not None:
            url += f"?after_id={after_id}"
        return self.client.get(url)

    def test_returns_at_most_50_without_after_id(self):
        data = self._get().json()
        self.assertLessEqual(len(data["messages"]), 50)

    def test_returns_messages_in_ascending_id_order(self):
        msgs = self._get().json()["messages"]
        ids = [m["id"] for m in msgs]
        self.assertEqual(ids, sorted(ids))

    def test_after_id_returns_only_newer_messages(self):
        all_ids = list(
            Message.objects.filter(room=self.room).order_by("id").values_list("id", flat=True)
        )
        cutoff = all_ids[29]
        data = self._get(after_id=cutoff).json()
        for msg in data["messages"]:
            self.assertGreater(msg["id"], cutoff)

    def test_after_id_respects_limit(self):
        data = self._get(after_id=0).json()
        self.assertLessEqual(len(data["messages"]), 50)

    def test_returns_empty_when_no_new_messages(self):
        last_id = Message.objects.filter(room=self.room).order_by("-id").first().id
        data = self._get(after_id=last_id).json()
        self.assertEqual(len(data["messages"]), 0)

    def test_message_has_required_fields(self):
        msgs = self._get().json()["messages"]
        self.assertTrue(len(msgs) > 0)
        for field in ("id", "username", "content", "timestamp", "message_type", "reactions"):
            self.assertIn(field, msgs[0])

    def test_private_room_returns_403(self):
        private = Room.objects.create(
            name="PrivPoll", slug="priv-poll", creator=self.creator,
            is_private=True, access_code="abc"
        )
        response = self.client.get(reverse("get_messages", args=[private.slug]))
        self.assertEqual(response.status_code, 403)

    def test_invalid_after_id_does_not_crash(self):
        url = reverse("get_messages", args=[self.room.slug]) + "?after_id=notanumber"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ===========================================================================
# Reactions Tests
# ===========================================================================

class ReactionTests(TestCase):

    def setUp(self):
        self.creator = make_user("reacter")
        self.room = Room.objects.create(
            name="React Room", slug="react-room", creator=self.creator
        )
        self.message = Message.objects.create(
            room=self.room, user=self.creator, content="React to this"
        )

    def test_add_reaction(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("toggle_message_reaction", args=[self.message.id]),
            data=json.dumps({"reaction": "❤️"}),
            content_type="application/json",
        )
        self.assertEqual(response.json()["action"], "added")
        self.assertTrue(
            MessageReaction.objects.filter(
                message=self.message, user=self.creator, reaction="❤️"
            ).exists()
        )

    def test_toggle_removes_reaction(self):
        self.client.force_login(self.creator)
        for _ in range(2):
            self.client.post(
                reverse("toggle_message_reaction", args=[self.message.id]),
                data=json.dumps({"reaction": "🔥"}),
                content_type="application/json",
            )
        self.assertFalse(
            MessageReaction.objects.filter(
                message=self.message, user=self.creator, reaction="🔥"
            ).exists()
        )

    def test_invalid_reaction_rejected(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("toggle_message_reaction", args=[self.message.id]),
            data=json.dumps({"reaction": "🐙"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reaction_requires_login(self):
        response = self.client.post(
            reverse("toggle_message_reaction", args=[self.message.id]),
            data=json.dumps({"reaction": "❤️"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)


# ===========================================================================
# AI Integration Tests
# ===========================================================================

class AIIntegrationTests(TestCase):

    def setUp(self):
        self.creator = make_user("ai_creator")
        self.viewer = make_user("ai_viewer")
        self.profile = UserProfile.objects.get(user=self.creator)
        AIIntegration.objects.create(
            profile=self.profile, provider="gpt", api_key="test-key"
        )
        self.room = Room.objects.create(
            name="AI Room", slug="ai-room", creator=self.creator
        )

    def test_creator_enables_ai_provider(self):
        self.client.force_login(self.creator)
        self.client.post(
            reverse("manage_room_ai_integrations", args=[self.room.slug]),
            {"providers": ["gpt"]}, follow=True,
        )
        self.assertTrue(
            RoomAIIntegration.objects.filter(room=self.room, provider="gpt").exists()
        )

    def test_non_creator_cannot_enable_ai(self):
        self.client.force_login(self.viewer)
        self.client.post(
            reverse("manage_room_ai_integrations", args=[self.room.slug]),
            {"providers": ["gpt"]}, follow=True,
        )
        self.assertFalse(
            RoomAIIntegration.objects.filter(room=self.room, provider="gpt").exists()
        )

    def test_ai_reply_sent_when_provider_enabled(self):
        self.client.force_login(self.creator)
        self.client.post(
            reverse("manage_room_ai_integrations", args=[self.room.slug]),
            {"providers": ["gpt"]},
        )
        self.client.logout()
        self.client.force_login(self.viewer)
        with patch("chat.views.fetch_ai_response", return_value=("AI says hi", 10)):
            response = self.client.post(
                reverse("send_message", args=[self.room.slug]),
                data=json.dumps({"content": "@gpt say something"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(content="AI says hi").exists())


# ===========================================================================
# Model Tests
# ===========================================================================

class ModelTests(TestCase):

    def setUp(self):
        self.user = make_user("modeluser")
        self.room = Room.objects.create(
            name="Model Room", slug="model-room", creator=self.user
        )

    def test_room_slug_auto_generated(self):
        room = Room.objects.create(name="Auto Slug Room", creator=self.user)
        self.assertTrue(bool(room.slug))

    def test_user_profile_created_on_registration(self):
        new_user = make_user("profiletest")
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())

    def test_user_profile_is_premium_false_by_default(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertFalse(profile.is_premium)

    def test_user_profile_room_limit_free(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.room_limit, 5)

    def test_message_reactions_summary_has_4_emojis(self):
        msg = Message.objects.create(
            room=self.room, user=self.user, content="No reactions"
        )
        summary = msg.get_reactions_summary()
        self.assertEqual(len(summary), 4)
        for item in summary:
            self.assertEqual(item["count"], 0)

    def test_total_messages_count_increments_on_new_message(self):
        profile = UserProfile.objects.get(user=self.user)
        initial = profile.total_messages_count
        Message.objects.create(room=self.room, user=self.user, content="count me")
        profile.refresh_from_db()
        self.assertEqual(profile.total_messages_count, initial + 1)

    def test_room_invitation_code_auto_generated(self):
        invite = RoomInvitation.objects.create(room=self.room, invited_by=self.user)
        self.assertTrue(bool(invite.invite_code))
        self.assertGreater(len(invite.invite_code), 4)


# ===========================================================================
# Cache Utils Tests
# ===========================================================================

class CacheUtilsTests(TestCase):

    def test_set_and_get(self):
        from .cache_utils import get_cache, set_cache
        self.assertTrue(set_cache("unit_test_key", {"v": 42}, timeout=60))
        self.assertEqual(get_cache("unit_test_key")["v"], 42)

    def test_delete_cache(self):
        from .cache_utils import set_cache, delete_cache, get_cache
        set_cache("del_test_key", "hello", timeout=60)
        delete_cache("del_test_key")
        self.assertIsNone(get_cache("del_test_key"))

    def test_room_messages_cache_lifecycle(self):
        from .cache_utils import (
            set_room_messages_cache, get_room_messages_cache,
            invalidate_room_messages_cache,
        )
        set_room_messages_cache("my-slug", [{"id": 1}], timeout=30)
        self.assertIsNotNone(get_room_messages_cache("my-slug"))
        invalidate_room_messages_cache("my-slug")
        self.assertIsNone(get_room_messages_cache("my-slug"))

    def test_invalidate_also_clears_api_cache(self):
        """invalidate_room_messages_cache must clear room_msgs_api_* too."""
        from .cache_utils import set_cache, get_cache, invalidate_room_messages_cache
        set_cache("room_msgs_api_test-slug", {"messages": []}, timeout=60)
        invalidate_room_messages_cache("test-slug")
        self.assertIsNone(get_cache("room_msgs_api_test-slug"))

    def test_user_avatar_cache(self):
        from .cache_utils import set_user_avatar, get_user_avatar, invalidate_user_avatar
        set_user_avatar(999, "https://example.com/avatar.jpg")
        self.assertEqual(get_user_avatar(999), "https://example.com/avatar.jpg")
        invalidate_user_avatar(999)
        self.assertIsNone(get_user_avatar(999))


# ===========================================================================
# normalize_email_canonical Tests
# ===========================================================================

class NormalizeEmailTests(TestCase):

    def _norm(self, email):
        from chat.views import normalize_email_canonical
        return normalize_email_canonical(email)

    def test_lowercase(self):
        self.assertEqual(self._norm("User@Gmail.COM"), "user@gmail.com")

    def test_gmail_removes_dots(self):
        self.assertEqual(self._norm("u.s.e.r@gmail.com"), "user@gmail.com")

    def test_gmail_removes_plus_alias(self):
        self.assertEqual(self._norm("user+tag@gmail.com"), "user@gmail.com")

    def test_googlemail_normalizes_to_gmail(self):
        self.assertEqual(self._norm("user@googlemail.com"), "user@gmail.com")

    def test_yandex_aliases_normalize(self):
        self.assertEqual(self._norm("user@ya.ru"), "user@yandex.ru")

    def test_regular_email_lowercased(self):
        self.assertEqual(self._norm("User@Example.com"), "user@example.com")

    def test_empty_string(self):
        self.assertEqual(self._norm(""), "")


# ===========================================================================
# parse_ai_command Tests
# ===========================================================================

class ParseAICommandTests(TestCase):

    def _parse(self, text):
        from chat.views import parse_ai_command
        return parse_ai_command(text)

    def test_at_gpt_command(self):
        alias, prompt = self._parse("@gpt Tell me a joke")
        self.assertEqual(alias, "gpt")
        self.assertIn("Tell me a joke", prompt)

    def test_at_gemini_command(self):
        alias, _ = self._parse("@gemini Explain AI")
        self.assertEqual(alias, "gemini")

    def test_no_at_returns_none_alias(self):
        alias, _ = self._parse("just a normal message")
        self.assertIsNone(alias)

    def test_multiword_prompt_preserved(self):
        alias, prompt = self._parse("@claude What is the meaning of life?")
        self.assertEqual(alias, "claude")
        self.assertIn("meaning of life", prompt)


# ===========================================================================
# SmartCaptcha _verify_smartcaptcha Tests
# ===========================================================================

class SmartCaptchaVerifyTests(TestCase):

    def test_returns_true_when_no_server_key(self):
        from chat.views import _verify_smartcaptcha
        with override_settings(SMARTCAPTCHA_SERVER_KEY=""):
            self.assertTrue(_verify_smartcaptcha("any-token", "1.2.3.4"))

    def test_returns_false_when_no_token(self):
        from chat.views import _verify_smartcaptcha
        with override_settings(SMARTCAPTCHA_SERVER_KEY="real-key"):
            self.assertFalse(_verify_smartcaptcha("", "1.2.3.4"))

    def test_returns_true_on_network_error(self):
        from chat.views import _verify_smartcaptcha
        with override_settings(SMARTCAPTCHA_SERVER_KEY="real-key"):
            with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
                self.assertTrue(_verify_smartcaptcha("some-token", "1.2.3.4"))

    def test_returns_true_on_ok_status(self):
        from chat.views import _verify_smartcaptcha
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok"}'
        with override_settings(SMARTCAPTCHA_SERVER_KEY="real-key"):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                self.assertTrue(_verify_smartcaptcha("valid-token", "1.2.3.4"))

    def test_returns_false_on_failed_status(self):
        from chat.views import _verify_smartcaptcha
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "failed"}'
        with override_settings(SMARTCAPTCHA_SERVER_KEY="real-key"):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                self.assertFalse(_verify_smartcaptcha("bad-token", "1.2.3.4"))


# ===========================================================================
# Pages Tests
# ===========================================================================

class PageTests(TestCase):

    def setUp(self):
        self.user = make_user("pageuser")
        self.room = Room.objects.create(
            name="Page Room", slug="page-room", creator=self.user
        )

    def test_landing_page_loads(self):
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)

    def test_landing_shows_stats_context(self):
        Message.objects.create(room=self.room, user=self.user, content="stat msg")
        response = self.client.get(reverse("landing"))
        self.assertIn("total_messages", response.context)

    def test_dashboard_accessible_to_anonymous(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_room_stats_page_loads(self):
        self.assertEqual(
            self.client.get(reverse("room_stats", args=[self.room.slug])).status_code, 200
        )

    def test_terms_privacy_contacts_load(self):
        for name in ("terms", "privacy", "contacts"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_login_required_pages_redirect(self):
        for name in ("profile", "ai_management", "achievements"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response.url)


# ===========================================================================
# Achievement Tests
# ===========================================================================

class AchievementTests(TestCase):

    def setUp(self):
        self.user = make_user("achiever")

    def test_registration_achievement_granted_on_signup(self):
        from .models import _ensure_achievements
        _ensure_achievements()
        new_user = make_user("newachieveuser")
        ach = Achievement.objects.filter(condition_type="registration").first()
        if ach:
            self.assertTrue(
                UserAchievement.objects.filter(user=new_user, achievement=ach).exists()
            )

    def test_achievements_page_loads(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("achievements")).status_code, 200)


# ===========================================================================
# Admin Tests
# ===========================================================================

class AdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser", email="admin@test.com", password="adminpass"
        )
        self.client.force_login(self.admin)

    def test_admin_index(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_admin_room_list(self):
        self.assertEqual(self.client.get(reverse("admin:chat_room_changelist")).status_code, 200)

    def test_admin_message_list(self):
        self.assertEqual(self.client.get(reverse("admin:chat_message_changelist")).status_code, 200)

    def test_admin_userprofile_list(self):
        self.assertEqual(self.client.get(reverse("admin:chat_userprofile_changelist")).status_code, 200)

    def test_admin_grant_premium(self):
        target = make_user("targetprem")
        self.client.post(
            reverse("admin:chat_userprofile_grant_premium_by_id"),
            {"user_id": target.id},
        )
        target.profile.refresh_from_db()
        self.assertTrue(target.profile.is_premium)

    def test_admin_grant_balance(self):
        target = make_user("targetbal")
        self.client.post(
            reverse("admin:chat_userprofile_grant_balance_by_id"),
            {"user_id": target.id, "amount": 500},
        )
        target.profile.refresh_from_db()
        self.assertEqual(target.profile.balance, 500)
