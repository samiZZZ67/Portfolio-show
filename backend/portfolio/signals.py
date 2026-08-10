from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EditorProfile


@receiver(post_save, sender=User)
def ensure_editor_profile(sender, instance, **kwargs):
    EditorProfile.objects.get_or_create(user=instance)
