import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Fetch recent Telegram bot updates and show chat IDs you can bind to editor profiles."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25, help="Maximum number of updates to request.")
        parser.add_argument(
            "--offset",
            type=int,
            default=None,
            help="Optional Telegram update offset.",
        )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured.")

        query = {"limit": max(1, min(int(options["limit"]), 100))}
        if options["offset"] is not None:
            query["offset"] = int(options["offset"])

        url = (
            f"{settings.TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates"
            f"?{urlencode(query)}"
        )
        response = urlopen(url, timeout=15)
        payload = json.loads(response.read().decode("utf-8") or "{}")
        if not payload.get("ok"):
            raise CommandError(f"Telegram getUpdates failed: {payload}")

        results = payload.get("result", [])
        if not results:
            self.stdout.write(
                self.style.WARNING(
                    "No Telegram updates found yet. Send a message like /start to your bot first."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Found {len(results)} Telegram update(s):"))
        for update in results:
            message = (
                update.get("message")
                or update.get("edited_message")
                or update.get("channel_post")
                or {}
            )
            chat = message.get("chat") or {}
            from_user = message.get("from") or {}
            text = (message.get("text") or "").replace("\n", " ").strip()
            self.stdout.write(
                (
                    f"- update_id={update.get('update_id')} "
                    f"chat_id={chat.get('id')} "
                    f"chat_type={chat.get('type', '')} "
                    f"username=@{from_user.get('username')}" if from_user.get("username") else
                    f"- update_id={update.get('update_id')} "
                    f"chat_id={chat.get('id')} "
                    f"chat_type={chat.get('type', '')}"
                )
            )
            self.stdout.write(
                f"  name={from_user.get('first_name', '')} {from_user.get('last_name', '')}".rstrip()
            )
            if text:
                self.stdout.write(f"  text={text}")
