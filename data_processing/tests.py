from django.test import TestCase
from django.utils import timezone
from .models import ParsingSchedule, ProcessedFile

class ParsingTestCase(TestCase):
    def setUp(self):
        self.schedule = ParsingSchedule.objects.create(
            name="Test Schedule",
            ftp_path="/test/path",
            schedule_cron="* * * * *",
            is_active=True
        )

    def test_scheduled_parse(self):
        from .tasks import scheduled_parse
        result = scheduled_parse.delay(self.schedule.id)
        self.assertIsNotNone(result.id)