from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction

from .models import (
    EditorProfile,
    PortfolioVideo,
    VideoCategory,
    VideoContentType,
    VideoSourceType,
)

RESERVED_USERNAMES = {
    "admin",
    "api",
    "auth",
    "dashboard",
    "discover",
    "media",
    "static",
}


class SignUpForm(forms.Form):
    username = forms.CharField(
        min_length=3,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "id": "signupUsername",
                "class": "input-field",
                "placeholder": "Choose a unique username (case-sensitive)",
            }
        ),
    )
    password = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "id": "signupPassword",
                "class": "input-field",
                "placeholder": "Min 6 characters",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "id": "signupEmail",
                "class": "input-field",
                "placeholder": "your@email.com",
            }
        ),
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "id": "signupBio",
                "class": "input-field",
                "placeholder": "Tell clients about yourself...",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username.lower() in RESERVED_USERNAMES:
            raise ValidationError("This username is reserved.")
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        temp_user = User(username=self.cleaned_data.get("username", ""))
        validate_password(password, user=temp_user)
        return password

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )
        profile = user.editor_profile
        profile.bio = self.cleaned_data["bio"] or EditorProfile.default_bio
        profile.save(update_fields=["bio", "updated_at"])
        return user


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "id": "loginUsername",
                "class": "input-field",
                "placeholder": "Your unique username",
            }
        )
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "id": "loginPassword",
                "class": "input-field",
                "placeholder": "Enter password",
            }
        ),
    )

    error_messages = {
        "invalid_login": "Invalid username or password.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise ValidationError(self.error_messages["invalid_login"])
            if not self.user_cache.is_active:
                raise ValidationError("This account is inactive.")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class ProfileForm(forms.ModelForm):
    class Meta:
        model = EditorProfile
        fields = ("bio", "avatar_url")
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "id": "editBio",
                    "class": "input-field",
                    "placeholder": "Tell clients about yourself and your editing style...",
                }
            ),
            "avatar_url": forms.URLInput(
                attrs={
                    "id": "editAvatar",
                    "class": "input-field",
                    "placeholder": "https://example.com/avatar.jpg",
                }
            ),
        }


class ContactForm(forms.Form):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "id": "contactEmail",
                "class": "input-field",
                "placeholder": "your@email.com",
            }
        ),
    )
    telegram = forms.CharField(
        required=False,
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "id": "contactTelegram",
                "class": "input-field",
                "placeholder": "@username",
            }
        ),
    )
    whatsapp = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "id": "contactWhatsapp",
                "class": "input-field",
                "placeholder": "+1234567890",
            }
        ),
    )
    phone = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "id": "contactPhone",
                "class": "input-field",
                "placeholder": "+1234567890",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            [
                cleaned_data.get("email"),
                cleaned_data.get("telegram"),
                cleaned_data.get("whatsapp"),
                cleaned_data.get("phone"),
            ]
        ):
            raise ValidationError("At least one contact method is required.")
        return cleaned_data

    def save(self, user, profile):
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["email"])
        profile.telegram = self.cleaned_data["telegram"]
        profile.whatsapp = self.cleaned_data["whatsapp"]
        profile.phone = self.cleaned_data["phone"]
        profile.save(update_fields=["telegram", "whatsapp", "phone", "updated_at"])
        return profile


class VideoForm(forms.ModelForm):
    uploaded_file = forms.FileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["mp4", "mov", "webm", "m4v", "avi"],
            )
        ],
    )
    video_source = forms.ChoiceField(
        choices=VideoSourceType.choices,
        initial=VideoSourceType.LINK,
        required=False,
    )

    class Meta:
        model = PortfolioVideo
        fields = (
            "title",
            "url",
            "video_source",
            "uploaded_file",
            "thumbnail_url",
            "content_type",
            "category",
            "duration",
        )
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "id": "videoTitle",
                    "class": "input-field",
                    "placeholder": "Give your video a title",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "id": "videoUrl",
                    "class": "input-field",
                    "placeholder": "YouTube, Vimeo, TikTok, or Instagram URL",
                }
            ),
            "thumbnail_url": forms.URLInput(
                attrs={
                    "id": "videoThumb",
                    "class": "input-field",
                    "placeholder": "https://example.com/thumbnail.jpg (optional)",
                }
            ),
            "content_type": forms.Select(
                attrs={
                    "id": "videoType",
                    "class": "input-field",
                }
            ),
            "category": forms.Select(
                attrs={
                    "id": "videoCategory",
                    "class": "input-field",
                }
            ),
            "duration": forms.TextInput(
                attrs={
                    "id": "videoDuration",
                    "class": "input-field",
                    "placeholder": "e.g. 3:45 or 0:30",
                }
            ),
        }

    content_type = forms.ChoiceField(
        choices=VideoContentType.choices,
        widget=forms.Select(
            attrs={
                "id": "videoType",
                "class": "input-field",
            }
        ),
    )
    category = forms.ChoiceField(
        choices=VideoCategory.choices,
        widget=forms.Select(
            attrs={
                "id": "videoCategory",
                "class": "input-field",
            }
        ),
    )

    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data.get("uploaded_file")
        if uploaded_file and uploaded_file.size > 250 * 1024 * 1024:
            raise ValidationError("Uploaded videos must be 250 MB or smaller.")
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("video_source") or VideoSourceType.LINK
        cleaned_data["video_source"] = source
        url = (cleaned_data.get("url") or "").strip()
        uploaded_file = cleaned_data.get("uploaded_file")
        has_existing_upload = bool(self.instance and self.instance.pk and self.instance.uploaded_file)

        if source == VideoSourceType.LINK:
            if not url:
                self.add_error("url", "A video link is required for link videos.")
        elif source == VideoSourceType.UPLOAD:
            if not uploaded_file and not has_existing_upload:
                self.add_error("uploaded_file", "Please choose a local video file to upload.")
            cleaned_data["url"] = ""
        elif source == VideoSourceType.BOTH:
            if not url:
                self.add_error("url", "A video link is required when source is set to both.")
            if not uploaded_file and not has_existing_upload:
                self.add_error("uploaded_file", "Please choose a local video file to upload.")

        return cleaned_data

    def save(self, commit=True):
        previous_file = None
        if self.instance and not self.instance._state.adding:
            previous_file = PortfolioVideo.objects.get(pk=self.instance.pk).uploaded_file

        video = super().save(commit=False)
        source = self.cleaned_data["video_source"]
        uploaded_file = self.cleaned_data.get("uploaded_file")

        if source == VideoSourceType.LINK:
            if previous_file:
                previous_file.delete(save=False)
            video.uploaded_file = None
        elif uploaded_file:
            if previous_file and previous_file.name and previous_file.name != uploaded_file.name:
                previous_file.delete(save=False)
            video.uploaded_file = uploaded_file

        if source == VideoSourceType.UPLOAD:
            video.url = ""

        if commit:
            video.save()
        return video


class VideoMoveForm(forms.Form):
    direction = forms.ChoiceField(choices=(("up", "Up"), ("down", "Down")))
