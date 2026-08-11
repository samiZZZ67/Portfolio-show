from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0010_skilltag_videodownloadrequest_telegram_chat_id_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="editorprofile",
            constraint=models.UniqueConstraint(
                condition=~models.Q(telegram=""),
                fields=("telegram",),
                name="unique_nonblank_editorprofile_telegram",
            ),
        ),
        migrations.AddConstraint(
            model_name="editorprofile",
            constraint=models.UniqueConstraint(
                condition=~models.Q(telegram_chat_id=""),
                fields=("telegram_chat_id",),
                name="unique_nonblank_editorprofile_telegram_chat_id",
            ),
        ),
    ]
