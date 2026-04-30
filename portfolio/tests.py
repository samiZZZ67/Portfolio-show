import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PortfolioVideo, VideoCategory, VideoContentType, VideoSourceType

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

    def test_signup_creates_user_profile_and_session(self):
        response = self.client.post(
            reverse("portfolio:signup"),
            {
                "username": "EditorOne",
                "password": "StrongPass123!",
                "email": "editorone@example.com",
                "bio": "Fast turnaround editor.",
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="EditorOne")
        self.assertEqual(user.email, "editorone@example.com")
        self.assertEqual(user.editor_profile.bio, "Fast turnaround editor.")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

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
                "whatsapp": "",
                "phone": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "At least one contact method is required.", status_code=400)

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
