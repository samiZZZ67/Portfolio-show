import os
import requests
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Set up Telegram webhook for the bot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain name for webhook URL (e.g., yoursite.com)',
            required=True
        )
        parser.add_argument(
            '--secret',
            type=str,
            help='Webhook secret (if not set, uses TELEGRAM_WEBHOOK_SECRET env var)'
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove webhook instead of setting it'
        )

    def handle(self, *args, **options):
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not bot_token:
            raise CommandError('TELEGRAM_BOT_TOKEN is not configured')

        domain = options['domain']
        secret = options.get('secret') or getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')

        if not secret:
            raise CommandError('TELEGRAM_WEBHOOK_SECRET is not configured. Use --secret or set env var.')

        if options['remove']:
            # Remove webhook
            url = f'https://api.telegram.org/bot{bot_token}/deleteWebhook'
            response = requests.post(url)
            if response.status_code == 200:
                self.stdout.write(
                    self.style.SUCCESS('Successfully removed Telegram webhook')
                )
            else:
                raise CommandError(f'Failed to remove webhook: {response.text}')
        else:
            # Set webhook
            webhook_url = f'https://{domain}/api/telegram/webhook/{secret}/'
            url = f'https://api.telegram.org/bot{bot_token}/setWebhook'
            data = {'url': webhook_url}

            response = requests.post(url, data=data)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully set webhook to: {webhook_url}')
                    )
                    # Get webhook info
                    info_url = f'https://api.telegram.org/bot{bot_token}/getWebhookInfo'
                    info_response = requests.get(info_url)
                    if info_response.status_code == 200:
                        info = info_response.json()
                        if info.get('ok'):
                            webhook_info = info.get('result', {})
                            self.stdout.write(f'Webhook URL: {webhook_info.get("url", "Not set")}')
                            self.stdout.write(f'Pending updates: {webhook_info.get("pending_update_count", 0)}')
                else:
                    raise CommandError(f'Failed to set webhook: {result.get("description", "Unknown error")}')
            else:
                raise CommandError(f'HTTP error {response.status_code}: {response.text}')