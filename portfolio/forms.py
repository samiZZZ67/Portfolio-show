import json
import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, URLValidator
from django.db import transaction

from .models import (
    AccountRole,
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
    role = forms.ChoiceField(
        required=False,
        choices=AccountRole.choices,
        initial=AccountRole.EDITOR,
    )
    cname = forms.CharField(
        required=False,
        max_length=150,
    )
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
    avatar_file = forms.FileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"],
            )
        ],
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

    def clean_avatar_file(self):
        avatar_file = self.cleaned_data.get("avatar_file")
        if avatar_file and avatar_file.size > 10 * 1024 * 1024:
            raise ValidationError("Profile images must be 10 MB or smaller.")
        return avatar_file

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )
        profile = user.editor_profile
        profile.role = self.cleaned_data.get("role") or AccountRole.EDITOR
        profile.cname = self.cleaned_data.get("cname", "").strip()
        profile.bio = self.cleaned_data["bio"] or EditorProfile.default_bio
        if self.cleaned_data.get("avatar_file"):
            profile.avatar_file = self.cleaned_data["avatar_file"]
        profile.save(update_fields=["role", "cname", "bio", "avatar_file", "updated_at"])
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
    username = forms.CharField(
        min_length=3,
        max_length=150,
    )
    cname = forms.CharField(required=False, max_length=150)
    avatar_file = forms.FileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"],
            )
        ],
    )

    class Meta:
        model = EditorProfile
        fields = ("cname", "bio", "avatar_url", "avatar_file")
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

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["username"].initial = self.user.username
        self.fields["cname"].initial = self.instance.cname

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username.lower() in RESERVED_USERNAMES:
            raise ValidationError("This username is reserved.")
        queryset = User.objects.filter(username=username).exclude(pk=self.user.pk)
        if queryset.exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_avatar_file(self):
        avatar_file = self.cleaned_data.get("avatar_file")
        if avatar_file and avatar_file.size > 10 * 1024 * 1024:
            raise ValidationError("Profile images must be 10 MB or smaller.")
        return avatar_file

    def save(self, commit=True):
        previous_avatar = None
        if self.instance and not self.instance._state.adding:
            previous_avatar = EditorProfile.objects.get(pk=self.instance.pk).avatar_file

        profile = super().save(commit=False)
        self.user.username = self.cleaned_data["username"]
        self.user.save(update_fields=["username"])
        profile.cname = self.cleaned_data["cname"].strip()

        avatar_file = self.cleaned_data.get("avatar_file")
        if avatar_file:
            if previous_avatar and previous_avatar.name and previous_avatar.name != avatar_file.name:
                previous_avatar.delete(save=False)
            profile.avatar_file = avatar_file

        if commit:
            profile.save()
        return profile


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
    other_contacts_json = forms.CharField(required=False)

    def clean_other_contacts_json(self):
        raw_value = self.cleaned_data.get("other_contacts_json", "").strip()
        if not raw_value:
            return []

        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValidationError("Additional contact links could not be read.") from exc

        if not isinstance(decoded, list):
            raise ValidationError("Additional contact links must be a list.")

        validate_url = URLValidator(schemes=["http", "https"])
        normalized_contacts = []
        for item in decoded:
            if not isinstance(item, dict):
                raise ValidationError("Each additional contact link must be an object.")
            label = str(item.get("label", "")).strip()
            value = str(item.get("value", "")).strip()
            if not label and not value:
                continue
            if not label or not value:
                raise ValidationError("Each additional contact link needs both a label and a URL.")
            if len(label) > 40:
                raise ValidationError("Additional contact labels must be 40 characters or fewer.")
            if not re.match(r"^https?://", value, re.IGNORECASE):
                value = f"https://{value}"
            validate_url(value)
            normalized_contacts.append(
                {
                    "label": label,
                    "value": value,
                }
            )
        return normalized_contacts

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            [
                cleaned_data.get("email"),
                cleaned_data.get("telegram"),
                cleaned_data.get("whatsapp"),
                cleaned_data.get("phone"),
                cleaned_data.get("other_contacts_json"),
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
        profile.other_contacts = self.cleaned_data["other_contacts_json"]
        profile.save(
            update_fields=["telegram", "whatsapp", "phone", "other_contacts", "updated_at"]
        )
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
