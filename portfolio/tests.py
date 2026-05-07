import json
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError
from django.test.client import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from .gemini import GeminiAPIError
from .groq import GROQ_HTTP_USER_AGENT, GroqAPIError, generate_groq_text
from .models import (
    AccountRole,
    DownloadRequestStatus,
    EditorSkill,
    EditorProfile,
    FollowRelationship,
    OwnerNotification,
    PortfolioVideo,
    SkillTag,
    VideoDownloadGrant,
    VideoDownloadRequest,
    VideoReaction,
    VideoStarRating,
    VideoCategory,
    VideoContentType,
    VideoPlatform,
    VideoReactionType,
    VideoSourceType,
    compact_upload_filename,
)
from .api_secure.throttles import SecureVideoDownloadRequestThrottle

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PortfolioApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def test_frontend_shell_injects_backend_bridge(self):
        response = self.client.get(reverse("portfolio:home"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("portfolio/js/backend_bridge.js", body)
        self.assertNotIn("password: 'demo123'", body)

    def test_frontend_shell_hides_admin_link_from_anonymous_visitors(self):
        response = self.client.get(reverse("portfolio:home"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        self.assertIn('id="desktopAccountLink"', body)
        self.assertIn('id="mobileAccountLink"', body)
        self.assertNotIn('id="desktopAdminLink"', body)
        self.assertNotIn('id="mobileAdminLink"', body)

    def test_frontend_shell_shows_public_about_links_and_login_feedback(self):
        response = self.client.get(reverse("portfolio:home"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('href="/about/" class="nav-link">About Me</a>', body)
        self.assertIn('href="/about/" class="nav-link" style="font-size:18px;"', body)
        self.assertIn('id="loginSubmitFeedback"', body)

    def test_frontend_shell_includes_google_auth_actions(self):
        response = self.client.get(reverse("portfolio:home"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('id="loginGoogleAction"', body)
        self.assertIn('id="signupGoogleAction"', body)
        self.assertIn('id="loginGoogleStatus"', body)
        self.assertIn('id="signupGoogleStatus"', body)

    def test_frontend_shell_serves_custom_admin_route(self):
        response = self.client.get(reverse("portfolio:admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('id="adminPage"', body)
        self.assertIn("Admin Dashboard", body)

    def test_about_page_is_public(self):
        response = self.client.get(reverse("portfolio:about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "About Me")
        self.assertNotContains(response, 'href="/admin/" class="nav-link"', html=False)

    def test_frontend_shell_renders_ai_assistant_markup(self):
        response = self.client.get(reverse("portfolio:home"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("AI Project Assistant", body)
        self.assertIn('id="userInput"', body)
        self.assertIn('id="groqSendBtn"', body)
        self.assertIn('id="geminiSendBtn"', body)
        self.assertIn('id="aiStatus"', body)
        self.assertIn('id="output"', body)

    @override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-2.5-flash")
    @patch("portfolio.views.generate_gemini_text", return_value="AI says hello.")
    def test_gemini_chat_returns_generated_reply(self, mock_generate_gemini_text):
        response = self.client.post(
            reverse("portfolio:gemini-chat"),
            data=json.dumps({"message": "Help me write a better editor bio."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reply"], "AI says hello.")
        self.assertEqual(payload["model"], "gemini-2.5-flash")
        mock_generate_gemini_text.assert_called_once_with("Help me write a better editor bio.")

    @override_settings(GEMINI_API_KEY="")
    def test_gemini_chat_requires_configuration(self):
        response = self.client.post(
            reverse("portfolio:gemini-chat"),
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["message"],
            "The AI assistant is not configured on this server yet.",
        )

    @override_settings(GEMINI_API_KEY="test-key")
    def test_gemini_chat_rejects_blank_message(self):
        response = self.client.post(
            reverse("portfolio:gemini-chat"),
            data=json.dumps({"message": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Please enter a message before sending.")

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("portfolio.views.generate_gemini_text", side_effect=GeminiAPIError("Upstream Gemini failed."))
    def test_gemini_chat_surfaces_upstream_errors(self, mock_generate_gemini_text):
        response = self.client.post(
            reverse("portfolio:gemini-chat"),
            data=json.dumps({"message": "Need a better social clip hook."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Upstream Gemini failed.")
        mock_generate_gemini_text.assert_called_once()

    @override_settings(GROQ_API_KEY="test-key", GROQ_MODEL="llama-3.1-8b-instant")
    @patch("portfolio.views.generate_groq_text", return_value="Groq says hello.")
    def test_groq_chat_returns_generated_reply(self, mock_generate_groq_text):
        response = self.client.post(
            reverse("portfolio:groq-chat"),
            data=json.dumps({"message": "Write a fast hook for a short-form ad."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reply"], "Groq says hello.")
        self.assertEqual(payload["model"], "llama-3.1-8b-instant")
        mock_generate_groq_text.assert_called_once_with("Write a fast hook for a short-form ad.")

    @override_settings(GROQ_API_KEY="")
    def test_groq_chat_requires_configuration(self):
        response = self.client.post(
            reverse("portfolio:groq-chat"),
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["message"], "Groq is not configured on this server yet.")

    @override_settings(GROQ_API_KEY="test-key")
    def test_groq_chat_rejects_blank_message(self):
        response = self.client.post(
            reverse("portfolio:groq-chat"),
            data=json.dumps({"message": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Please enter a message before sending.")

    @override_settings(GROQ_API_KEY="test-key")
    @patch("portfolio.views.generate_groq_text", side_effect=GroqAPIError("Upstream Groq failed."))
    def test_groq_chat_surfaces_upstream_errors(self, mock_generate_groq_text):
        response = self.client.post(
            reverse("portfolio:groq-chat"),
            data=json.dumps({"message": "Need a faster ad concept."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Upstream Groq failed.")
        mock_generate_groq_text.assert_called_once()

    @override_settings(GROQ_API_KEY="test-key", GROQ_MODEL="llama-3.1-8b-instant")
    @patch("portfolio.groq.request.urlopen")
    def test_generate_groq_text_sends_browser_compatible_headers(self, mock_urlopen):
        captured = {}

        class FakeGroqResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "ok",
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeGroqResponse()

        mock_urlopen.side_effect = fake_urlopen

        reply = generate_groq_text("Reply with exactly: ok")

        self.assertEqual(reply, "ok")
        self.assertEqual(captured["headers"]["User-agent"], GROQ_HTTP_USER_AGENT)
        self.assertEqual(captured["headers"]["Accept"], "application/json")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")


    @override_settings(TELEGRAM_BOT_TOKEN="test-bot-token", TELEGRAM_WEBHOOK_SECRET="secret123")
    @patch("portfolio.api_secure.services.send_telegram_message", return_value="tg-message-1")
    def test_telegram_webhook_returns_ok_when_matching_username_is_duplicated(self, mock_send_telegram):
        with patch(
            "portfolio.models.EditorProfile.objects.get",
            side_effect=EditorProfile.MultipleObjectsReturned,
        ):
            response = self.client.post(
                reverse("portfolio:telegram-webhook", args=["secret123"]),
                data=json.dumps(
                    {
                        "message": {
                            "chat": {"id": 99887766, "username": "eloicry"},
                            "text": "/start",
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        mock_send_telegram.assert_called_once()

    @override_settings(TELEGRAM_BOT_TOKEN="test-bot-token", TELEGRAM_WEBHOOK_SECRET="secret123")
    @patch("portfolio.api_secure.services.send_telegram_message", return_value="tg-message-2")
    def test_telegram_webhook_returns_ok_when_chat_id_save_fails(self, mock_send_telegram):
        owner = User.objects.create_user(
            username="WebhookOwner",
            password="SecurePass123!",
            email="webhookowner@example.com",
        )
        owner.editor_profile.telegram = "@eloicry"
        owner.editor_profile.save(update_fields=["telegram"])
        original_save = EditorProfile.save

        def flaky_save(instance, *args, **kwargs):
            if instance.pk == owner.editor_profile.pk and kwargs.get("update_fields") == ["telegram_chat_id"]:
                raise DatabaseError("chat id save failed")
            return original_save(instance, *args, **kwargs)

        with patch("portfolio.models.EditorProfile.save", autospec=True, side_effect=flaky_save):
            response = self.client.post(
                reverse("portfolio:telegram-webhook", args=["secret123"]),
                data=json.dumps(
                    {
                        "message": {
                            "chat": {"id": 99887766, "username": "eloicry"},
                            "text": "/start",
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        owner.editor_profile.refresh_from_db()
        self.assertEqual(owner.editor_profile.telegram_chat_id, "")
        mock_send_telegram.assert_called_once()

    def test_ensure_admin_user_creates_superuser_from_environment(self):
        with patch.dict(
            "os.environ",
            {
                "DJANGO_SUPERUSER_USERNAME": "renderadmin",
                "DJANGO_SUPERUSER_EMAIL": "renderadmin@example.com",
                "DJANGO_SUPERUSER_PASSWORD": "RenderPass123!",
            },
            clear=False,
        ):
            output = StringIO()
            call_command("ensure_admin_user", stdout=output)

        user = User.objects.get(username="renderadmin")
        self.assertEqual(user.email, "renderadmin@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("RenderPass123!"))
        self.assertIn("Created admin user 'renderadmin'.", output.getvalue())

    def test_ensure_admin_user_repairs_existing_user_permissions(self):
        user = User.objects.create_user(
            username="existingrenderadmin",
            email="old@example.com",
            password="OldPass123!",
        )
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.save()

        with patch.dict(
            "os.environ",
            {
                "DJANGO_SUPERUSER_USERNAME": "existingrenderadmin",
                "DJANGO_SUPERUSER_EMAIL": "new@example.com",
                "DJANGO_SUPERUSER_PASSWORD": "NewPass123!",
            },
            clear=False,
        ):
            output = StringIO()
            call_command("ensure_admin_user", stdout=output)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("NewPass123!"))
        self.assertIn("Verified admin user 'existingrenderadmin'.", output.getvalue())

    def test_signup_creates_user_profile_and_session(self):
        response = self.client.post(
            reverse("portfolio:signup"),
            {
                "role": AccountRole.EDITOR,
                "cname": "Studio Alpha",
                "username": "EditorOne",
                "password": "StrongPass123!",
                "email": "editorone@example.com",
                "telegram": "@editorone",
                "bio": "Fast turnaround editor.",
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="EditorOne")
        self.assertEqual(user.email, "editorone@example.com")
        self.assertEqual(user.editor_profile.bio, "Fast turnaround editor.")
        self.assertEqual(user.editor_profile.cname, "Studio Alpha")
        self.assertEqual(user.editor_profile.role, AccountRole.EDITOR)
        self.assertEqual(user.editor_profile.telegram, "@editorone")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_editor_signup_requires_telegram_binding(self):
        response = self.client.post(
            reverse("portfolio:signup"),
            {
                "role": AccountRole.EDITOR,
                "cname": "No Telegram Studio",
                "username": "NoTelegramEditor",
                "password": "StrongPass123!",
                "email": "notelegram@example.com",
                "bio": "Missing Telegram.",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="NoTelegramEditor").exists())
        self.assertContains(
            response,
            "Editor accounts must include a Telegram username or Telegram chat ID.",
            status_code=400,
        )

    def test_public_signup_rejects_admin_role(self):
        response = self.client.post(
            reverse("portfolio:signup"),
            {
                "role": AccountRole.ADMIN,
                "cname": "Back Office",
                "username": "AdminSignupAttempt",
                "password": "StrongPass123!",
                "email": "adminsignup@example.com",
                "bio": "Should not be allowed.",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="AdminSignupAttempt").exists())

    def test_cname_is_not_unique_but_username_is(self):
        first = self.client.post(
            reverse("portfolio:signup"),
            {
                "role": AccountRole.EDITOR,
                "cname": "Shared Studio",
                "username": "SharedOne",
                "password": "StrongPass123!",
                "email": "sharedone@example.com",
                "telegram": "@sharedone",
                "bio": "First account.",
            },
        )
        self.assertEqual(first.status_code, 201)
        self.client.post(reverse("portfolio:logout"))

        second = self.client.post(
            reverse("portfolio:signup"),
            {
                "role": AccountRole.CLIENT,
                "cname": "Shared Studio",
                "username": "SharedTwo",
                "password": "StrongPass123!",
                "email": "sharedtwo@example.com",
                "bio": "Second account.",
            },
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(User.objects.filter(editor_profile__cname="Shared Studio").count(), 2)

    def test_login_rejects_invalid_credentials(self):
        User.objects.create_user(
            username="EditorTwo",
            password="CorrectHorse123!",
            email="editortwo@example.com",
        )
        response = self.client.post(
            reverse("portfolio:login"),
            {
                "username": "EditorTwo",
                "password": "wrong-password",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid username or password.", status_code=400)

    def test_login_returns_success_message_and_session(self):
        user = User.objects.create_user(
            username="EditorLogin",
            password="CorrectHorse123!",
            email="editorlogin@example.com",
        )
        response = self.client.post(
            reverse("portfolio:login"),
            {
                "username": "EditorLogin",
                "password": "CorrectHorse123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Login successful.")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_bootstrap_exposes_google_auth_as_unavailable_without_credentials(self):
        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["google_auth_available"])
        self.assertEqual(payload["google_auth_url"], reverse("portfolio:google-login-start"))
        self.assertIn("GOOGLE_OAUTH_CLIENT_ID", payload["google_auth_message"])

    @override_settings(
        GOOGLE_OAUTH_CONFIG_ERROR="Conflicting values were found for: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_CLIENT_ID."
    )
    def test_bootstrap_surfaces_google_auth_config_conflicts(self):
        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["google_auth_available"])
        self.assertIn("Conflicting values were found", payload["google_auth_message"])

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APP": {
                    "client_id": "test-google-client-id",
                    "secret": "test-google-client-secret",
                    "key": "",
                }
            }
        }
    )
    def test_bootstrap_exposes_google_auth_when_configured(self):
        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["google_auth_available"])
        self.assertEqual(payload["google_auth_url"], reverse("portfolio:google-login-start"))
        self.assertEqual(payload["google_auth_message"], "Continue with Google for a faster sign-in.")

    def test_google_login_start_view_renders_unavailable_page_when_unconfigured(self):
        response = self.client.get(reverse("portfolio:google-login-start"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Google auth is not ready yet", status_code=503)

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APP": {
                    "client_id": "test-google-client-id",
                    "secret": "test-google-client-secret",
                    "key": "",
                }
            }
        }
    )
    def test_google_login_start_view_redirects_to_provider_with_next_path(self):
        response = self.client.get(
            reverse("portfolio:google-login-start"),
            {"next": "/admin/"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/google/login/", response["Location"])
        self.assertIn("next=%2Fadmin%2F", response["Location"])

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APP": {
                    "client_id": "test-google-client-id",
                    "secret": "test-google-client-secret",
                    "key": "",
                }
            }
        }
    )
    def test_allauth_google_login_route_is_not_captured_by_portfolio_catchall(self):
        response = self.client.get("/accounts/google/login/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])

    def test_bootstrap_marks_staff_users_as_admin_capable(self):
        admin_user = User.objects.create_superuser(
            username="AdminBootstrap",
            password="SecurePass123!",
            email="adminbootstrap@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_user"], "AdminBootstrap")
        self.assertTrue(payload["current_user_can_access_admin"])

    def test_bootstrap_marks_regular_users_as_not_admin_capable(self):
        user = User.objects.create_user(
            username="RegularBootstrap",
            password="SecurePass123!",
            email="regularbootstrap@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_user"], "RegularBootstrap")
        self.assertFalse(payload["current_user_can_access_admin"])

    @override_settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL="gemini-2.5-flash",
        GROQ_API_KEY="groq-key",
        GROQ_MODEL="llama-3.1-8b-instant",
    )
    def test_bootstrap_exposes_ai_configuration(self):
        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["groq_enabled"])
        self.assertEqual(payload["groq_model"], "llama-3.1-8b-instant")
        self.assertTrue(payload["gemini_enabled"])
        self.assertEqual(payload["gemini_model"], "gemini-2.5-flash")

    def test_admin_overview_requires_admin_access(self):
        user = User.objects.create_user(
            username="NoAdminOverview",
            password="SecurePass123!",
            email="viewer@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("portfolio:secure-admin-overview"))

        self.assertEqual(response.status_code, 403)

    def test_admin_overview_returns_summary_for_role_admin(self):
        admin_user = User.objects.create_user(
            username="RoleAdminOverview",
            password="SecurePass123!",
            email="roleadmin@example.com",
        )
        admin_user.editor_profile.role = AccountRole.ADMIN
        admin_user.editor_profile.save(update_fields=["role"])
        editor_user = User.objects.create_user(
            username="OverviewEditor",
            password="SecurePass123!",
            email="editor@example.com",
        )
        PortfolioVideo.objects.create(
            profile=editor_user.editor_profile,
            title="Overview Reel",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("portfolio:secure-admin-overview"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["users_total"], User.objects.count())
        self.assertEqual(
            payload["summary"]["admins_total"],
            EditorProfile.objects.filter(role=AccountRole.ADMIN).count(),
        )
        self.assertEqual(payload["summary"]["videos_total"], PortfolioVideo.objects.count())
        usernames = [profile["username"] for profile in payload["profiles"]]
        self.assertIn("RoleAdminOverview", usernames)
        self.assertIn("OverviewEditor", usernames)

    def test_admin_role_update_endpoint_changes_profile_role(self):
        admin_user = User.objects.create_user(
            username="RoleManager",
            password="SecurePass123!",
            email="manager@example.com",
        )
        admin_user.editor_profile.role = AccountRole.ADMIN
        admin_user.editor_profile.save(update_fields=["role"])
        target_user = User.objects.create_user(
            username="RoleTarget",
            password="SecurePass123!",
            email="target@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("portfolio:secure-admin-profile-role", args=[target_user.username]),
            data=json.dumps({"role": AccountRole.CLIENT}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        target_user.editor_profile.refresh_from_db()
        self.assertEqual(target_user.editor_profile.role, AccountRole.CLIENT)
        self.assertEqual(response.json()["profile"]["role"], AccountRole.CLIENT)

    def test_editor_profile_link_is_public_and_case_insensitive(self):
        user = User.objects.create_user(
            username="ElaShare",
            password="CorrectHorse123!",
            email="",
        )
        PortfolioVideo.objects.create(
            profile=user.editor_profile,
            title="Shareable Reel",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )

        response = self.client.get("/elashare/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portfolio/js/backend_bridge.js", status_code=200)
        self.assertContains(response, "ElaShare", status_code=200)

        bootstrap = self.client.get(reverse("portfolio:bootstrap")).json()
        self.assertTrue(
            any(editor["username"] == "ElaShare" for editor in bootstrap["editors"])
        )

    def test_direct_profile_url_handles_unicode_seo_content(self):
        user = User.objects.create_user(
            username="ElaUnicode",
            password="CorrectHorse123!",
            email="elaunicode@example.com",
        )
        user.editor_profile.cname = "Ela's"
        user.editor_profile.bio = (
            "Editing is more than cutting clips \u2014 it\u2019s about rhythm, emotion, and meaning."
        )
        user.editor_profile.phone = "+251900000099"
        user.editor_profile.save(update_fields=["cname", "bio", "phone"])

        response = self.client.get("/ElaUnicode/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ela&#x27;s (@ElaUnicode)", status_code=200)
        self.assertContains(response, "portfolio/js/backend_bridge.js", status_code=200)

    def test_invalid_profile_username_returns_friendly_404(self):
        response = self.client.get("/Bad!Name/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We couldn", status_code=404)

    def test_search_endpoint_filters_existing_portfolios(self):
        response = self.client.get(
            reverse("portfolio:search"),
            {
                "q": "Wedding",
                "type": "all",
                "category": "Wedding",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(editor["username"] == "WeddingFrames" for editor in payload["editors"]))
        self.assertFalse(any(editor["username"] == "CineMaster_Pro" for editor in payload["editors"]))

    def test_contacts_require_at_least_one_value(self):
        user = User.objects.create_user(
            username="EditorThree",
            password="SecurePass123!",
            email="editorthree@example.com",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("portfolio:contact-update"),
            {
                "email": "",
                "telegram": "",
                "telegram_chat_id": "",
                "whatsapp": "",
                "phone": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "At least one contact method is required.", status_code=400)

    def test_contact_update_saves_other_links(self):
        user = User.objects.create_user(
            username="EditorLinks",
            password="SecurePass123!",
            email="editorlinks@example.com",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("portfolio:contact-update"),
            {
                "email": "editorlinks@example.com",
                "telegram": "@editorlinks",
                "telegram_chat_id": "",
                "whatsapp": "",
                "phone": "",
                "other_contacts_json": '[{"label":"LinkedIn","value":"linkedin.com/in/editorlinks"}]',
            },
        )
        self.assertEqual(response.status_code, 200)
        user.editor_profile.refresh_from_db()
        self.assertEqual(
            user.editor_profile.other_contacts,
            [{"label": "LinkedIn", "value": "https://linkedin.com/in/editorlinks"}],
        )

    def test_editor_contact_update_requires_telegram_binding(self):
        user = User.objects.create_user(
            username="EditorNeedsTelegram",
            password="SecurePass123!",
            email="editorneedstelegram@example.com",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("portfolio:contact-update"),
            {
                "email": "editorneedstelegram@example.com",
                "telegram": "",
                "telegram_chat_id": "",
                "whatsapp": "+251900000000",
                "phone": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "Editor accounts must keep a Telegram username or Telegram chat ID on file.",
            status_code=400,
        )

    def test_bootstrap_returns_logged_in_editor_portfolio(self):
        user = User.objects.create_user(
            username="EditorPortfolio",
            password="SecurePass123!",
            email="portfolio@example.com",
        )
        PortfolioVideo.objects.create(
            profile=user.editor_profile,
            title="My First Reel",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("portfolio:bootstrap"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_user"], "EditorPortfolio")
        own_editor = next(
            editor for editor in payload["editors"] if editor["username"] == "EditorPortfolio"
        )
        self.assertEqual(own_editor["videos"][0]["title"], "My First Reel")
        self.assertEqual(own_editor["role"], AccountRole.EDITOR)

    def test_bootstrap_marks_pending_download_request_for_non_owner(self):
        owner = User.objects.create_user(
            username="VideoOwnerPending",
            password="SecurePass123!",
            email="ownerpending@example.com",
        )
        requester = User.objects.create_user(
            username="VideoRequesterPending",
            password="SecurePass123!",
            email="requesterpending@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Private Uploaded Cut",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "pending-access.mp4",
                b"video-bytes",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
        )
        VideoDownloadRequest.objects.create(
            requester=requester,
            video=video,
            status=DownloadRequestStatus.PENDING,
            telegram_chat_id="99887766",
            telegram_message_id="delivered-message-1",
        )

        self.client.force_login(requester)
        payload = self.client.get(reverse("portfolio:bootstrap")).json()

        owner_payload = next(
            editor for editor in payload["editors"] if editor["username"] == owner.username
        )
        video_payload = next(item for item in owner_payload["videos"] if item["id"] == str(video.id))
        self.assertEqual(video_payload["download_access_state"], DownloadRequestStatus.PENDING)
        self.assertIn(
            f"/api/secure/videos/{video.id}/download-request/",
            video_payload["request_access_url"],
        )

    def test_bootstrap_marks_failed_delivery_request_as_retryable(self):
        owner = User.objects.create_user(
            username="VideoOwnerRetry",
            password="SecurePass123!",
            email="ownerretry@example.com",
        )
        requester = User.objects.create_user(
            username="VideoRequesterRetry",
            password="SecurePass123!",
            email="requesterretry@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Retry Uploaded Cut",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "retry-access.mp4",
                b"video-bytes",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
        )
        VideoDownloadRequest.objects.create(
            requester=requester,
            video=video,
            status=DownloadRequestStatus.PENDING,
            telegram_chat_id="99887766",
            telegram_message_id="",
        )

        self.client.force_login(requester)
        payload = self.client.get(reverse("portfolio:bootstrap")).json()

        owner_payload = next(
            editor for editor in payload["editors"] if editor["username"] == owner.username
        )
        video_payload = next(item for item in owner_payload["videos"] if item["id"] == str(video.id))
        self.assertEqual(video_payload["download_access_state"], "delivery_failed")

    def test_bootstrap_marks_approved_download_access_for_granted_user(self):
        owner = User.objects.create_user(
            username="VideoOwnerApproved",
            password="SecurePass123!",
            email="ownerapproved@example.com",
        )
        requester = User.objects.create_user(
            username="VideoRequesterApproved",
            password="SecurePass123!",
            email="requesterapproved@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Approved Download Cut",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "approved-access.mp4",
                b"video-bytes",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.LONG,
            category=VideoCategory.DOCUMENTARY,
            duration="4:12",
        )
        download_request = VideoDownloadRequest.objects.create(
            requester=requester,
            video=video,
            status=DownloadRequestStatus.APPROVED,
        )
        VideoDownloadGrant.objects.create(
            user=requester,
            video=video,
            source_request=download_request,
            is_active=True,
        )

        self.client.force_login(requester)
        payload = self.client.get(reverse("portfolio:bootstrap")).json()

        owner_payload = next(
            editor for editor in payload["editors"] if editor["username"] == owner.username
        )
        video_payload = next(item for item in owner_payload["videos"] if item["id"] == str(video.id))
        self.assertEqual(video_payload["download_access_state"], DownloadRequestStatus.APPROVED)
        self.assertFalse(video_payload["can_download"])
        self.assertEqual(video_payload["download_url"], "")
        self.assertIn(
            f"/api/secure/videos/{video.id}/download-request/",
            video_payload["request_access_url"],
        )
        self.assertIn(
            f"/api/secure/videos/{video.id}/download/",
            video_payload["secure_download_url"],
        )

    def test_bootstrap_does_not_mark_approved_request_without_active_grant_as_downloadable(self):
        owner = User.objects.create_user(
            username="VideoOwnerNoGrant",
            password="SecurePass123!",
            email="ownernogrant@example.com",
        )
        requester = User.objects.create_user(
            username="VideoRequesterNoGrant",
            password="SecurePass123!",
            email="requesternogrant@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Approved Request Without Grant",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "approved-no-grant.mp4",
                b"video-bytes",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
        )
        VideoDownloadRequest.objects.create(
            requester=requester,
            video=video,
            status=DownloadRequestStatus.APPROVED,
        )

        self.client.force_login(requester)
        payload = self.client.get(reverse("portfolio:bootstrap")).json()

        owner_payload = next(
            editor for editor in payload["editors"] if editor["username"] == owner.username
        )
        video_payload = next(item for item in owner_payload["videos"] if item["id"] == str(video.id))
        self.assertEqual(video_payload["download_access_state"], "none")
        self.assertFalse(video_payload["can_download"])
        self.assertEqual(video_payload["download_url"], "")
        self.assertIn(
            f"/api/secure/videos/{video.id}/download-request/",
            video_payload["request_access_url"],
        )

    def test_profile_update_supports_username_cname_and_avatar_upload(self):
        user = User.objects.create_user(
            username="EditorRename",
            password="SecurePass123!",
            email="editorrename@example.com",
        )
        self.client.force_login(user)
        avatar = SimpleUploadedFile("avatar.png", b"avatar-bytes", content_type="image/png")
        response = self.client.post(
            reverse("portfolio:profile-update"),
            {
                "username": "EditorRenamed",
                "cname": "Renamed Studio",
                "clients_served": 12,
                "completed_projects": 48,
                "bio": "Updated bio",
                "avatar_url": "",
                "avatar_file": avatar,
            },
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "EditorRenamed")
        self.assertEqual(user.editor_profile.cname, "Renamed Studio")
        self.assertEqual(user.editor_profile.clients_served, 12)
        self.assertEqual(user.editor_profile.completed_projects, 48)
        self.assertTrue(user.editor_profile.avatar_file.name.endswith("avatar.png"))

    def test_bootstrap_includes_editor_skills(self):
        user = User.objects.create_user(
            username="SkilledEditor",
            password="SecurePass123!",
            email="skilleditor@example.com",
        )
        skill = SkillTag.objects.create(name="DaVinci Resolve")
        EditorSkill.objects.create(profile=user.editor_profile, skill=skill)

        response = self.client.get(reverse("portfolio:bootstrap"))

        self.assertEqual(response.status_code, 200)
        skilled_profile = next(
            editor for editor in response.json()["editors"] if editor["username"] == "SkilledEditor"
        )
        self.assertEqual(skilled_profile["skills"], ["DaVinci Resolve"])

    def test_follow_toggle_requires_login_and_persists(self):
        follower = User.objects.create_user(
            username="FollowerUser",
            password="SecurePass123!",
            email="follower@example.com",
        )
        target = User.objects.create_user(
            username="TargetUser",
            password="SecurePass123!",
            email="target@example.com",
        )
        target.editor_profile.phone = "+123456789"
        target.editor_profile.save()

        unauthenticated = self.client.post(
            reverse("portfolio:follow-toggle", kwargs={"username": "TargetUser"})
        )
        self.assertEqual(unauthenticated.status_code, 401)

        self.client.force_login(follower)
        first = self.client.post(
            reverse("portfolio:follow-toggle", kwargs={"username": "TargetUser"})
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(
            FollowRelationship.objects.filter(
                follower=follower.editor_profile,
                followed=target.editor_profile,
            ).exists()
        )

        second = self.client.post(
            reverse("portfolio:follow-toggle", kwargs={"username": "TargetUser"})
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(
            FollowRelationship.objects.filter(
                follower=follower.editor_profile,
                followed=target.editor_profile,
            ).exists()
        )

    def test_client_accounts_cannot_create_videos(self):
        user = User.objects.create_user(
            username="ClientOnly",
            password="SecurePass123!",
            email="clientonly@example.com",
        )
        user.editor_profile.role = AccountRole.CLIENT
        user.editor_profile.save(update_fields=["role"])
        self.client.force_login(user)
        response = self.client.post(
            reverse("portfolio:video-create"),
            {
                "title": "Should Fail",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "thumbnail_url": "",
                "content_type": VideoContentType.LONG,
                "category": VideoCategory.CORPORATE,
                "duration": "3:45",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_friendly_not_found_page_replaces_default_404(self):
        response = self.client.get("/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We couldn’t find that page.", status_code=404)

    def test_sitemap_and_robots_routes_exist(self):
        response = self.client.get(reverse("portfolio:sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<urlset", status_code=200)

        robots = self.client.get(reverse("portfolio:robots"))
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, "Sitemap:", status_code=200)

    def test_video_crud_flow(self):
        user = User.objects.create_user(
            username="EditorFour",
            password="SecurePass123!",
            email="editorfour@example.com",
        )
        self.client.force_login(user)

        create_response = self.client.post(
            reverse("portfolio:video-create"),
            {
                "title": "Brand Launch Cut",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "thumbnail_url": "",
                "content_type": VideoContentType.LONG,
                "category": VideoCategory.CORPORATE,
                "duration": "3:45",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        video = PortfolioVideo.objects.get(profile=user.editor_profile)

        update_response = self.client.post(
            reverse("portfolio:video-update", kwargs={"video_id": video.id}),
            {
                "title": "Updated Brand Launch Cut",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "thumbnail_url": "",
                "content_type": VideoContentType.SHORT,
                "category": VideoCategory.SOCIAL_MEDIA,
                "duration": "0:30",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        video.refresh_from_db()
        self.assertEqual(video.title, "Updated Brand Launch Cut")
        self.assertEqual(video.content_type, VideoContentType.SHORT)

        delete_response = self.client.post(
            reverse("portfolio:video-delete", kwargs={"video_id": video.id}),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(PortfolioVideo.objects.filter(pk=video.id).exists())

    def test_video_create_supports_local_upload(self):
        user = User.objects.create_user(
            username="EditorUpload",
            password="SecurePass123!",
            email="editorupload@example.com",
        )
        self.client.force_login(user)

        uploaded_file = SimpleUploadedFile(
            "showreel.mp4",
            b"fake-video-content",
            content_type="video/mp4",
        )
        response = self.client.post(
            reverse("portfolio:video-create"),
            {
                "title": "Uploaded Reel",
                "url": "",
                "video_source": VideoSourceType.UPLOAD,
                "thumbnail_url": "",
                "content_type": VideoContentType.SHORT,
                "category": VideoCategory.SOCIAL_MEDIA,
                "duration": "0:30",
                "uploaded_file": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["message"], "Video uploaded successfully.")
        video = PortfolioVideo.objects.get(profile=user.editor_profile)
        self.assertEqual(video.video_source, VideoSourceType.UPLOAD)
        self.assertEqual(video.url, "")
        self.assertTrue(video.uploaded_file.name.endswith("showreel.mp4"))

    def test_video_create_supports_both_link_and_upload(self):
        user = User.objects.create_user(
            username="EditorBoth",
            password="SecurePass123!",
            email="editorboth@example.com",
        )
        self.client.force_login(user)

        uploaded_file = SimpleUploadedFile(
            "campaign.mov",
            b"fake-video-content",
            content_type="video/quicktime",
        )
        response = self.client.post(
            reverse("portfolio:video-create"),
            {
                "title": "Hybrid Campaign",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "video_source": VideoSourceType.BOTH,
                "thumbnail_url": "",
                "content_type": VideoContentType.LONG,
                "category": VideoCategory.CORPORATE,
                "duration": "3:45",
                "uploaded_file": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 201)
        video = PortfolioVideo.objects.get(profile=user.editor_profile)
        self.assertEqual(video.video_source, VideoSourceType.BOTH)
        self.assertEqual(video.url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(video.uploaded_file.name.endswith("campaign.mov"))

    def test_video_upload_path_stays_short_for_long_filenames(self):
        user = User.objects.create_user(
            username="EditorLongName",
            password="SecurePass123!",
            email="editorlongname@example.com",
        )
        self.client.force_login(user)

        uploaded_file = SimpleUploadedFile(
            "From_3M_to_a_1_4B_empire_selli_btHmVce.mp4",
            b"fake-video-content",
            content_type="video/mp4",
        )
        response = self.client.post(
            reverse("portfolio:video-create"),
            {
                "title": "Compact Upload Path",
                "url": "",
                "video_source": VideoSourceType.UPLOAD,
                "thumbnail_url": "",
                "content_type": VideoContentType.SHORT,
                "category": VideoCategory.SOCIAL_MEDIA,
                "duration": "0:30",
                "uploaded_file": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 201)
        video = PortfolioVideo.objects.get(profile=user.editor_profile)
        self.assertLess(len(video.uploaded_file.name), 100)
        self.assertTrue(video.uploaded_file.name.startswith(f"v/{user.editor_profile.id}/"))
        self.assertTrue(video.uploaded_file.name.endswith(".mp4"))

    def test_cloudinary_media_fields_allow_long_public_ids(self):
        self.assertEqual(EditorProfile._meta.get_field("avatar_file").max_length, 500)
        self.assertEqual(PortfolioVideo._meta.get_field("uploaded_file").max_length, 500)

    def test_compact_upload_filename_preserves_extension(self):
        compact_name = compact_upload_filename(
            "From_3M_to_a_1_4B_empire_selli_btHmVce.mp4",
            default_stem="video",
            max_stem_length=16,
        )
        self.assertTrue(compact_name.endswith(".mp4"))
        self.assertLessEqual(len(compact_name.rsplit(".", 1)[0]), 16)

    def test_secure_video_upload_endpoint_saves_metadata(self):
        user = User.objects.create_user(
            username="SecureUploader",
            password="SecurePass123!",
            email="secureuploader@example.com",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("portfolio:secure-video-upload"),
            {
                "title": "Secure Reel",
                "uploaded_file": SimpleUploadedFile(
                    "secure-reel.mp4",
                    b"fake-video-content",
                    content_type="video/mp4",
                ),
                "platform": VideoPlatform.TIKTOK,
                "content_type": VideoContentType.SHORT,
                "category": VideoCategory.SOCIAL_MEDIA,
                "duration": "0:30",
                "original_width": 1080,
                "original_height": 1920,
                "watermark_enabled": "on",
            },
        )

        self.assertEqual(response.status_code, 201)
        video = PortfolioVideo.objects.get(profile=user.editor_profile, title="Secure Reel")
        self.assertEqual(video.video_source, VideoSourceType.UPLOAD)
        self.assertEqual(video.platform, VideoPlatform.TIKTOK)
        self.assertEqual(video.original_filename, "secure-reel.mp4")
        self.assertEqual(video.original_format, "mp4")
        self.assertEqual(video.original_width, 1080)
        self.assertEqual(video.original_height, 1920)

    def test_public_secure_stream_session_returns_signed_local_endpoint(self):
        user = User.objects.create_user(
            username="SecureStreamer",
            password="SecurePass123!",
            email="securestreamer@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=user.editor_profile,
            title="Secure Stream",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "secure-stream.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="secure-stream.mp4",
            original_format="mp4",
        )

        response = self.client.get(reverse("portfolio:secure-video-stream", args=[video.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("/api/secure/videos/", payload["stream_url"])
        self.assertTrue(payload["watermark"]["enabled"])

        token = payload["stream_url"].split("token=", 1)[1]
        stream_file_response = self.client.get(
            reverse("portfolio:secure-video-stream-file", args=[video.id]),
            {"token": token},
        )
        self.assertEqual(stream_file_response.status_code, 200)
        self.assertIn("inline;", stream_file_response["Content-Disposition"])

    def test_public_secure_like_and_rating_work_without_login(self):
        user = User.objects.create_user(
            username="SecureReactOwner",
            password="SecurePass123!",
            email="securereactowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=user.editor_profile,
            title="Engagement Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "engagement.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="engagement.mp4",
            original_format="mp4",
        )

        like_response = self.client.post(reverse("portfolio:secure-video-like", args=[video.id]))
        self.assertEqual(like_response.status_code, 200)
        self.assertEqual(like_response.json()["like_count"], 1)

        rating_response = self.client.post(
            reverse("portfolio:secure-video-rate", args=[video.id]),
            {"score": 5},
        )
        self.assertEqual(rating_response.status_code, 200)
        self.assertEqual(rating_response.json()["average_rating"], 5.0)
        self.assertEqual(rating_response.json()["ratings_count"], 1)

    def test_secure_download_request_requires_authentication(self):
        user = User.objects.create_user(
            username="SecureDownloadOwner",
            password="SecurePass123!",
            email="securedownloadowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=user.editor_profile,
            title="Private Download Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "private-download.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="private-download.mp4",
            original_format="mp4",
        )

        response = self.client.post(reverse("portfolio:secure-video-download-request", args=[video.id]))
        self.assertEqual(response.status_code, 403)

    def test_secure_download_request_approval_and_download_flow(self):
        owner = User.objects.create_user(
            username="SecureOwner",
            password="SecurePass123!",
            email="secureowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Approved Download Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "approved-download.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="approved-download.mp4",
            original_format="mp4",
        )

        requester = User.objects.create_user(
            username="SecureClient",
            password="SecurePass123!",
            email="secureclient@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        create_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(create_response.status_code, 201)
        download_request = VideoDownloadRequest.objects.get(requester=requester, video=video)
        self.assertEqual(download_request.status, DownloadRequestStatus.PENDING)
        self.assertTrue(OwnerNotification.objects.filter(owner=owner, video=video).exists())
        mail.outbox.clear()

        self.client.force_login(owner)
        review_response = self.client.post(
            reverse("portfolio:secure-owner-download-review", args=[download_request.id]),
            {"status": DownloadRequestStatus.APPROVED, "owner_response_message": "Approved."},
        )
        self.assertEqual(review_response.status_code, 200)
        download_request.refresh_from_db()
        self.assertEqual(download_request.status, DownloadRequestStatus.APPROVED)
        self.assertTrue(
            VideoDownloadGrant.objects.filter(
                user=requester,
                video=video,
                source_request=download_request,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            any(
                message.subject == "Download request approved"
                and requester.email in message.to
                and "Approved Download Reel" in message.body
                for message in mail.outbox
            )
        )

        notifications_response = self.client.get(reverse("portfolio:secure-owner-notifications"))
        self.assertEqual(notifications_response.status_code, 200)
        self.assertGreaterEqual(len(notifications_response.json()), 1)

        notification_id = notifications_response.json()[0]["id"]
        mark_read_response = self.client.post(
            reverse("portfolio:secure-owner-notification-read", args=[notification_id])
        )
        self.assertEqual(mark_read_response.status_code, 200)
        self.assertTrue(mark_read_response.json()["is_read"])

        self.client.force_login(requester)
        direct_download_response = self.client.get(
            reverse(
                "portfolio:video-download",
                kwargs={"username": owner.username, "video_id": video.id},
            )
        )
        self.assertEqual(direct_download_response.status_code, 403)

        link_response = self.client.get(reverse("portfolio:secure-video-download", args=[video.id]))
        self.assertEqual(link_response.status_code, 200)
        download_url = link_response.json()["download_url"]
        token = download_url.split("token=", 1)[1]

        file_response = self.client.get(
            reverse("portfolio:secure-video-download-file", args=[video.id]),
            {"token": token},
        )
        self.assertEqual(file_response.status_code, 200)
        self.assertIn("attachment;", file_response["Content-Disposition"])

    def test_secure_download_link_rejects_non_owner_without_approved_request_backed_grant(self):
        owner = User.objects.create_user(
            username="GrantOwner",
            password="SecurePass123!",
            email="grantowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Grant Protected Download",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "grant-protected.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="grant-protected.mp4",
            original_format="mp4",
        )

        requester = User.objects.create_user(
            username="GrantRequester",
            password="SecurePass123!",
            email="grantrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        VideoDownloadGrant.objects.create(
            user=requester,
            video=video,
            is_active=True,
        )

        self.client.force_login(requester)
        link_response = self.client.get(reverse("portfolio:secure-video-download", args=[video.id]))
        self.assertEqual(link_response.status_code, 403)

    @patch("portfolio.api_secure.services.send_telegram_message", return_value="tg-message-123")
    def test_secure_download_request_response_confirms_owner_telegram_delivery(self, mock_send_telegram):
        owner = User.objects.create_user(
            username="TelegramOwner",
            password="SecurePass123!",
            email="telegramowner@example.com",
        )
        owner.editor_profile.telegram = "@telegramowner"
        owner.editor_profile.telegram_chat_id = "99887766"
        owner.editor_profile.save(update_fields=["telegram", "telegram_chat_id"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Telegram Delivered Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "telegram-delivered.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="telegram-delivered.mp4",
            original_format="mp4",
        )
        requester = User.objects.create_user(
            username="TelegramRequester",
            password="SecurePass123!",
            email="telegramrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["delivery_confirmed"])
        self.assertEqual(payload["delivery_status"], "telegram_delivered")
        self.assertIn("successfully delivered", payload["delivery_message"].lower())

        download_request = VideoDownloadRequest.objects.get(requester=requester, video=video)
        self.assertEqual(download_request.telegram_chat_id, "99887766")
        self.assertEqual(download_request.telegram_message_id, "tg-message-123")
        mock_send_telegram.assert_called_once()

    def test_secure_download_request_throttle_uses_authenticated_user_identity(self):
        throttle = SecureVideoDownloadRequestThrottle()
        factory = RequestFactory()
        user = User.objects.create_user(
            username="ThrottleOwner",
            password="SecurePass123!",
            email="throttleowner@example.com",
        )

        first_request = factory.post("/api/secure/videos/demo/download-request/")
        first_request.user = user
        first_request.META["REMOTE_ADDR"] = "127.0.0.1"

        second_request = factory.post("/api/secure/videos/demo/download-request/")
        second_request.user = user
        second_request.META["REMOTE_ADDR"] = "203.0.113.10"

        anonymous_request = factory.post("/api/secure/videos/demo/download-request/")
        anonymous_request.user = AnonymousUser()
        anonymous_request.META["REMOTE_ADDR"] = "127.0.0.1"

        first_key = throttle.get_cache_key(first_request, view=None)
        second_key = throttle.get_cache_key(second_request, view=None)
        anonymous_key = throttle.get_cache_key(anonymous_request, view=None)

        self.assertEqual(first_key, second_key)
        self.assertNotEqual(first_key, anonymous_key)
        self.assertIn(f"user:{user.pk}", first_key)

    def test_secure_download_request_resolves_owner_chat_id_from_telegram_updates(self):
        owner = User.objects.create_user(
            username="LinkedTelegramOwner",
            password="SecurePass123!",
            email="linkedtelegramowner@example.com",
        )
        owner.editor_profile.telegram = "@linkedtelegramowner"
        owner.editor_profile.telegram_chat_id = ""
        owner.editor_profile.save(update_fields=["telegram", "telegram_chat_id"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Resolved Telegram Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "resolved-telegram.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="resolved-telegram.mp4",
            original_format="mp4",
        )
        requester = User.objects.create_user(
            username="ResolvedTelegramRequester",
            password="SecurePass123!",
            email="resolvedtelegramrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        with patch(
            "portfolio.api_secure.services.fetch_telegram_updates",
            return_value=[
                {
                    "update_id": 7001,
                    "message": {
                        "chat": {"id": 44332211, "type": "private"},
                        "from": {"username": "LinkedTelegramOwner"},
                        "text": "/start",
                    },
                }
            ],
        ) as mock_fetch_updates, patch(
            "portfolio.api_secure.services.send_telegram_message",
            return_value="tg-message-linked",
        ) as mock_send_telegram:
            self.client.force_login(requester)
            response = self.client.post(
                reverse("portfolio:secure-video-download-request", args=[video.id]),
                {"request_message": "Please approve this download."},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["delivery_confirmed"])
        self.assertEqual(payload["delivery_status"], "telegram_delivered")
        owner.editor_profile.refresh_from_db()
        self.assertEqual(owner.editor_profile.telegram_chat_id, "44332211")

        download_request = VideoDownloadRequest.objects.get(requester=requester, video=video)
        self.assertEqual(download_request.telegram_chat_id, "44332211")
        self.assertEqual(download_request.telegram_message_id, "tg-message-linked")
        mock_fetch_updates.assert_called_once()
        mock_send_telegram.assert_called_once_with(
            "44332211",
            mock_send_telegram.call_args.args[1],
        )

    @patch("portfolio.api_secure.services.send_telegram_message", return_value="tg-message-999")
    def test_second_request_is_blocked_after_successful_delivery(self, mock_send_telegram):
        owner = User.objects.create_user(
            username="DeliveredOwner",
            password="SecurePass123!",
            email="deliveredowner@example.com",
        )
        owner.editor_profile.telegram = "@deliveredowner"
        owner.editor_profile.telegram_chat_id = "66554433"
        owner.editor_profile.save(update_fields=["telegram", "telegram_chat_id"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Already Delivered Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "already-delivered.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="already-delivered.mp4",
            original_format="mp4",
        )
        requester = User.objects.create_user(
            username="DeliveredRequester",
            password="SecurePass123!",
            email="deliveredrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        first_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(first_response.status_code, 201)

        second_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download again."},
        )
        self.assertEqual(second_response.status_code, 400)
        self.assertContains(
            second_response,
            "Your request is already pending review.",
            status_code=400,
        )
        self.assertEqual(
            VideoDownloadRequest.objects.filter(requester=requester, video=video).count(),
            1,
        )
        self.assertEqual(mock_send_telegram.call_count, 1)

    @patch("portfolio.api_secure.services.fetch_telegram_updates", return_value=[])
    def test_secure_download_request_missing_owner_chat_id_falls_back_to_admin_notification(self, mock_fetch_updates):
        owner = User.objects.create_user(
            username="FallbackOwner",
            password="SecurePass123!",
            email="fallbackowner@example.com",
        )
        owner.editor_profile.telegram = "@fallbackowner"
        owner.editor_profile.telegram_chat_id = ""
        owner.editor_profile.save(update_fields=["telegram", "telegram_chat_id"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Fallback Download Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "fallback-download.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="fallback-download.mp4",
            original_format="mp4",
        )
        admin_user = User.objects.create_superuser(
            username="FallbackAdmin",
            password="SecurePass123!",
            email="fallbackadmin@example.com",
        )
        admin_user.editor_profile.role = AccountRole.ADMIN
        admin_user.editor_profile.save(update_fields=["role"])
        requester = User.objects.create_user(
            username="FallbackRequester",
            password="SecurePass123!",
            email="fallbackrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertFalse(payload["delivery_confirmed"])
        self.assertEqual(payload["delivery_status"], "admin_fallback_missing_owner_chat_id")
        self.assertEqual(
            payload["delivery_message"],
            "Your request was saved, but the video owner has not connected a Telegram chat ID yet. "
            "An admin was notified to follow up.",
        )

        admin_notification = OwnerNotification.objects.filter(
            owner=admin_user,
            video=video,
            download_request__requester=requester,
        ).order_by("-id").first()
        self.assertIsNotNone(admin_notification)
        self.assertEqual(admin_notification.payload.get("reason"), "missing_owner_chat_id")
        mock_fetch_updates.assert_called_once()

    @patch("portfolio.api_secure.services.send_telegram_message", side_effect=RuntimeError("telegram failed"))
    def test_secure_download_request_reports_failed_owner_telegram_delivery(self, mock_send_telegram):
        owner = User.objects.create_user(
            username="BrokenTelegramOwner",
            password="SecurePass123!",
            email="brokentelegramowner@example.com",
        )
        owner.editor_profile.telegram = "@brokentelegramowner"
        owner.editor_profile.telegram_chat_id = "55443322"
        owner.editor_profile.save(update_fields=["telegram", "telegram_chat_id"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Broken Telegram Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "broken-telegram.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="broken-telegram.mp4",
            original_format="mp4",
        )
        admin_user = User.objects.create_superuser(
            username="BrokenTelegramAdmin",
            password="SecurePass123!",
            email="brokentelegramadmin@example.com",
        )
        admin_user.editor_profile.role = AccountRole.ADMIN
        admin_user.editor_profile.save(update_fields=["role"])
        requester = User.objects.create_user(
            username="BrokenTelegramRequester",
            password="SecurePass123!",
            email="brokentelegramrequester@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertFalse(payload["delivery_confirmed"])
        self.assertEqual(payload["delivery_status"], "admin_fallback_delivery_failed")
        self.assertEqual(
            payload["delivery_message"],
            "Your request was saved, but we couldn't confirm Telegram delivery to the video owner. "
            "An admin was notified to follow up.",
        )

        admin_notification = OwnerNotification.objects.filter(
            owner=admin_user,
            video=video,
            download_request__requester=requester,
        ).order_by("-id").first()
        self.assertIsNotNone(admin_notification)
        self.assertEqual(admin_notification.payload.get("reason"), "owner_telegram_delivery_failed")
        mock_send_telegram.assert_called_once()

        retry_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Trying again after failed delivery."},
        )
        self.assertEqual(retry_response.status_code, 201)
        retry_payload = retry_response.json()
        self.assertFalse(retry_payload["delivery_confirmed"])
        self.assertEqual(retry_payload["delivery_status"], "admin_fallback_delivery_failed")
        self.assertEqual(
            retry_payload["delivery_message"],
            "Your request was saved, but we couldn't confirm Telegram delivery to the video owner. "
            "An admin was notified to follow up.",
        )
        self.assertEqual(
            VideoDownloadRequest.objects.filter(requester=requester, video=video).count(),
            1,
        )
        self.assertEqual(mock_send_telegram.call_count, 2)

    def test_requester_receives_email_when_download_request_is_rejected(self):
        owner = User.objects.create_user(
            username="RejectOwner",
            password="SecurePass123!",
            email="rejectowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Rejected Download Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "rejected-download.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="rejected-download.mp4",
            original_format="mp4",
        )
        requester = User.objects.create_user(
            username="RejectClient",
            password="SecurePass123!",
            email="rejectclient@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        create_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Please approve this download."},
        )
        self.assertEqual(create_response.status_code, 201)
        download_request = VideoDownloadRequest.objects.get(requester=requester, video=video)
        mail.outbox.clear()

        self.client.force_login(owner)
        review_response = self.client.post(
            reverse("portfolio:secure-owner-download-review", args=[download_request.id]),
            {"status": DownloadRequestStatus.REJECTED, "owner_response_message": "Not available."},
        )
        self.assertEqual(review_response.status_code, 200)
        download_request.refresh_from_db()
        self.assertEqual(download_request.status, DownloadRequestStatus.REJECTED)
        self.assertFalse(
            VideoDownloadGrant.objects.filter(
                user=requester,
                video=video,
                source_request=download_request,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            any(
                message.subject == "Download request rejected"
                and requester.email in message.to
                and "Rejected Download Reel" in message.body
                for message in mail.outbox
            )
        )

    def test_admin_can_review_download_request_and_create_grant(self):
        owner = User.objects.create_user(
            username="RequestOwner",
            password="SecurePass123!",
            email="requestowner@example.com",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Reviewable Reel",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=SimpleUploadedFile(
                "reviewable.mp4",
                b"fake-video-content",
                content_type="video/mp4",
            ),
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
            original_filename="reviewable.mp4",
            original_format="mp4",
        )
        requester = User.objects.create_user(
            username="RequestClient",
            password="SecurePass123!",
            email="requestclient@example.com",
        )
        requester.editor_profile.role = AccountRole.CLIENT
        requester.editor_profile.save(update_fields=["role"])

        self.client.force_login(requester)
        create_response = self.client.post(
            reverse("portfolio:secure-video-download-request", args=[video.id]),
            {"request_message": "Need the approved file."},
        )
        self.assertEqual(create_response.status_code, 201)
        download_request = VideoDownloadRequest.objects.get(requester=requester, video=video)

        admin_user = User.objects.create_superuser(
            username="ReviewAdmin",
            password="SecurePass123!",
            email="reviewadmin@example.com",
        )
        admin_user.editor_profile.role = AccountRole.ADMIN
        admin_user.editor_profile.save(update_fields=["role"])

        self.client.force_login(admin_user)
        review_response = self.client.post(
            reverse("portfolio:secure-owner-download-review", args=[download_request.id]),
            {"status": DownloadRequestStatus.APPROVED, "owner_response_message": "Admin approved."},
        )
        self.assertEqual(review_response.status_code, 200)
        download_request.refresh_from_db()
        self.assertEqual(download_request.reviewed_by, admin_user)
        self.assertTrue(
            VideoDownloadGrant.objects.filter(
                user=requester,
                video=video,
                source_request=download_request,
                is_active=True,
            ).exists()
        )

    def test_admin_index_uses_custom_dashboard(self):
        admin_user = User.objects.create_superuser(
            username="AdminUser",
            password="SecurePass123!",
            email="admin@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ela-sam Admin")
        self.assertContains(response, "Portfolio Control Center")
        self.assertContains(response, "Everything important is one click away.")

    def test_admin_user_change_page_shows_portfolio_profile_inline(self):
        admin_user = User.objects.create_superuser(
            username="AdminInline",
            password="SecurePass123!",
            email="admininline@example.com",
        )
        managed_user = User.objects.create_user(
            username="ManagedUser",
            password="SecurePass123!",
            email="managed@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:auth_user_change", args=[managed_user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editor profile")
        self.assertContains(response, "Open public profile")

    def test_video_like_and_star_rating_flow(self):
        owner = User.objects.create_user(
            username="ReactionOwner",
            password="SecurePass123!",
            email="reactionowner@example.com",
        )
        owner.editor_profile.phone = "+251900000001"
        owner.editor_profile.save(update_fields=["phone"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Reaction Reel",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )

        reactor = User.objects.create_user(
            username="ReactionClient",
            password="SecurePass123!",
            email="reactionclient@example.com",
        )
        self.client.force_login(reactor)

        like_response = self.client.post(
            reverse(
                "portfolio:video-like",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
        )
        self.assertEqual(like_response.status_code, 200)
        self.assertEqual(
            VideoReaction.objects.filter(
                video=video,
                profile=reactor.editor_profile,
                reaction_type=VideoReactionType.LIKE,
            ).count(),
            1,
        )

        unlike_response = self.client.post(
            reverse(
                "portfolio:video-like",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
        )
        self.assertEqual(unlike_response.status_code, 200)
        self.assertEqual(
            VideoReaction.objects.filter(
                video=video,
                profile=reactor.editor_profile,
                reaction_type=VideoReactionType.LIKE,
            ).count(),
            0,
        )

        relike_response = self.client.post(
            reverse(
                "portfolio:video-like",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
        )
        self.assertEqual(relike_response.status_code, 200)

        rating_response = self.client.post(
            reverse(
                "portfolio:video-rate",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
            {"rating": 5},
        )
        self.assertEqual(rating_response.status_code, 200)
        self.assertEqual(
            VideoStarRating.objects.filter(video=video, profile=reactor.editor_profile).count(),
            1,
        )
        self.assertEqual(
            VideoStarRating.objects.get(video=video, profile=reactor.editor_profile).rating,
            5,
        )

        rerate_response = self.client.post(
            reverse(
                "portfolio:video-rate",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
            {"rating": 3},
        )
        self.assertEqual(rerate_response.status_code, 200)
        self.assertEqual(
            VideoStarRating.objects.filter(video=video, profile=reactor.editor_profile).count(),
            1,
        )
        self.assertEqual(
            VideoStarRating.objects.get(video=video, profile=reactor.editor_profile).rating,
            3,
        )

        second_reactor = User.objects.create_user(
            username="SecondReactor",
            password="SecurePass123!",
            email="secondreactor@example.com",
        )
        self.client.force_login(second_reactor)
        second_rating_response = self.client.post(
            reverse(
                "portfolio:video-rate",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
            {"rating": 5},
        )
        self.assertEqual(second_rating_response.status_code, 200)

        payload = second_rating_response.json()
        owner_payload = next(
            editor for editor in payload["editors"] if editor["username"] == owner.username
        )
        video_payload = next(item for item in owner_payload["videos"] if item["id"] == str(video.id))
        self.assertEqual(video_payload["likes_count"], 1)
        self.assertFalse(video_payload["viewer_has_liked"])
        self.assertEqual(video_payload["ratings_count"], 2)
        self.assertEqual(video_payload["average_rating"], 4.0)
        self.assertEqual(video_payload["viewer_rating"], 5)

    def test_video_like_and_rating_require_login(self):
        owner = User.objects.create_user(
            username="ProtectedOwner",
            password="SecurePass123!",
            email="protectedowner@example.com",
        )
        owner.editor_profile.phone = "+251900000005"
        owner.editor_profile.save(update_fields=["phone"])
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Protected Reel",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )

        like_response = self.client.post(
            reverse(
                "portfolio:video-like",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
        )
        self.assertEqual(like_response.status_code, 401)

        rating_response = self.client.post(
            reverse(
                "portfolio:video-rate",
                kwargs={"username": owner.username, "video_id": video.id},
            ),
            {"rating": 4},
        )
        self.assertEqual(rating_response.status_code, 401)

    def test_uploaded_video_download_is_owner_only(self):
        owner = User.objects.create_user(
            username="DownloadOwner",
            password="SecurePass123!",
            email="downloadowner@example.com",
        )
        owner.editor_profile.phone = "+251900000002"
        owner.editor_profile.save(update_fields=["phone"])
        uploaded_file = SimpleUploadedFile(
            "private-cut.mp4",
            b"binary-video",
            content_type="video/mp4",
        )
        video = PortfolioVideo.objects.create(
            profile=owner.editor_profile,
            title="Private Uploaded Cut",
            video_source=VideoSourceType.UPLOAD,
            uploaded_file=uploaded_file,
            content_type=VideoContentType.SHORT,
            category=VideoCategory.SOCIAL_MEDIA,
            duration="0:30",
            sort_order=0,
        )

        outsider = User.objects.create_user(
            username="DownloadOutsider",
            password="SecurePass123!",
            email="downloadoutsider@example.com",
        )
        self.client.force_login(outsider)

        stream_response = self.client.get(
            reverse(
                "portfolio:video-stream",
                kwargs={"username": owner.username, "video_id": video.id},
            )
        )
        self.assertEqual(stream_response.status_code, 200)
        self.assertIn("inline;", stream_response["Content-Disposition"])

        forbidden_download = self.client.get(
            reverse(
                "portfolio:video-download",
                kwargs={"username": owner.username, "video_id": video.id},
            )
        )
        self.assertEqual(forbidden_download.status_code, 403)

        self.client.force_login(owner)
        allowed_download = self.client.get(
            reverse(
                "portfolio:video-download",
                kwargs={"username": owner.username, "video_id": video.id},
            )
        )
        self.assertEqual(allowed_download.status_code, 200)
        self.assertIn("attachment;", allowed_download["Content-Disposition"])

    def test_uploaded_avatar_is_served_from_backend_endpoint(self):
        user = User.objects.create_user(
            username="AvatarOwner",
            password="SecurePass123!",
            email="avatarowner@example.com",
        )
        user.editor_profile.phone = "+251900000003"
        user.editor_profile.avatar_file = SimpleUploadedFile(
            "avatar.png",
            b"avatar-binary",
            content_type="image/png",
        )
        user.editor_profile.save(update_fields=["phone", "avatar_file"])

        response = self.client.get(
            reverse("portfolio:profile-avatar", kwargs={"username": user.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline;", response["Content-Disposition"])

        bootstrap = self.client.get(reverse("portfolio:bootstrap")).json()
        profile_payload = next(
            editor for editor in bootstrap["editors"] if editor["username"] == user.username
        )
        self.assertIn(f"/api/profiles/{user.username}/avatar/", profile_payload["avatar"])
