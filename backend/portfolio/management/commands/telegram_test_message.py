from django.core.management.base import BaseCommand, CommandError

from portfolio.api_secure.services import send_telegram_message


class Command(BaseCommand):
    help = "Send a Telegram test message to a specific chat ID."

    def add_arguments(self, parser):
        parser.add_argument("chat_id", help="Telegram chat ID to send the test message to.")
        parser.add_argument(
            "--text",
            default="Ela-sam Portfolio Show test message: Telegram delivery is working.",
            help="Message text to send.",
        )

    def handle(self, *args, **options):
        chat_id = str(options["chat_id"]).strip()
        text = str(options["text"]).strip()
        if not chat_id:
            raise CommandError("A Telegram chat ID is required.")
        if not text:
            raise CommandError("The message text cannot be empty.")

        message_id = send_telegram_message(chat_id, text)
        self.stdout.write(
            self.style.SUCCESS(
                f"Telegram test message sent successfully. message_id={message_id}"
            )
        )
