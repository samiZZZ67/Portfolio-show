import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

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

    def test_frontend_shell_shows_admin_link_for_anonymous_visitors(self):
        response = self.client.get(reverse("portfolio:home"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        desktop_account_index = body.index('id="desktopAccountLink"')
        desktop_admin_index = body.index('id="desktopAdminLink"')
        mobile_account_index = body.index('id="mobileAccountLink"')
        mobile_admin_index = body.index('id="mobileAdminLink"')

        self.assertLess(desktop_account_index, desktop_admin_index)
        self.assertLess(mobile_account_index, mobile_admin_index)

        desktop_admin_slice = body[max(0, desktop_admin_index - 120): desktop_admin_index + 160]
        mobile_admin_slice = body[max(0, mobile_admin_index - 120): mobile_admin_index + 160]

        self.assertNotIn("display:none", desktop_admin_slice)
        self.assertNotIn("display:none", mobile_admin_slice)

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
                "bio": "Fast turnaround editor.",
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="EditorOne")
        self.assertEqual(user.email, "editorone@example.com")
        self.assertEqual(user.editor_profile.bio, "Fast turnaround editor.")
        self.assertEqual(user.editor_profile.cname, "Studio Alpha")
        self.assertEqual(user.editor_profile.role, AccountRole.EDITOR)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

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
                "telegram": "",
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
        self.assertIn(
            f"/api/secure/videos/{video.id}/download/",
            video_payload["secure_download_url"],
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
