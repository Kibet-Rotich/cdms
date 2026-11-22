from django.core.management.base import BaseCommand

from core.events import process_pending


class Command(BaseCommand):
    help = "Re-deliver domain events that have not been processed yet."

    def handle(self, *args, **options):
        count = process_pending()
        self.stdout.write(self.style.SUCCESS(f"Processed {count} pending event(s)."))
