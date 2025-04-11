import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator

class Profile(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Manager', 'Manager'),
        ('Operator', 'Operator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Operator')

    def __str__(self):
        return f'{self.user.username} - {self.role}'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class OEEDailyData(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField()
    TotalProduction = models.FloatField(null=True, blank=True)
    TotalEmptyOut = models.FloatField(null=True, blank=True)
    ProductionBatches = models.IntegerField(null=True, blank=True)
    EmptyOutBatches = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = 'oee_daily_data'
 
class PlantRunTime(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField()
    MixingActive = models.FloatField(null=True, blank=True)
    Mixer = models.FloatField(null=True, blank=True)
    Screen = models.FloatField(null=True, blank=True)   
    HotElevator = models.FloatField(null=True, blank=True)
    Dryer = models.FloatField(null=True, blank=True)
    BurnerFlameOn = models.FloatField(null=True, blank=True)
    SlingerForward = models.FloatField(null=True, blank=True)
    SlingerReverse = models.FloatField(null=True, blank=True)
    CollectConveyor = models.FloatField(null=True, blank=True)
    DustBlower = models.FloatField(null=True, blank=True)
    DustBlowerRotaryValve = models.FloatField(null=True, blank=True)
    class Meta:
        db_table = 'plant_run_time'
 
class DailyRecipes(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField()
    RecipeNo = models.IntegerField(null=True, blank=True)
    RecipeName = models.CharField(max_length=255, null=True, blank=True)
    Total = models.FloatField(null=True, blank=True)
    class Meta:
        db_table = 'daily_recipes'
 
class DailyMaterials(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField()
    MaterialNo = models.IntegerField(null=True, blank=True)
    MaterialName = models.CharField(max_length=255, null=True, blank=True)
    Quantity = models.FloatField(null=True, blank=True)
    class Meta:
        db_table = 'daily_materials'

class EnergyData(models.Model):
    date = models.DateField(null=True, blank=True)
    meter_name = models.CharField(max_length=100, null=True, blank=True)
    value = models.FloatField(null=True, blank=True)  # From API's "value" field
    consumption = models.FloatField(null=True, blank=True)  # From API's "consumption" field
    timestamp = models.DateTimeField(null=True, blank=True)  # From API's "timestamp"

    class Meta:
        verbose_name = "Energy Meter Data"
        indexes = [
            models.Index(fields=['date', 'meter_name']),
        ]

    def __str__(self):
        return f"{self.meter_name} - {self.date}"
    

class BatchLog(models.Model):
    id = models.AutoField(primary_key=True)
    BatchNo = models.IntegerField(db_index=True) 
    Time = models.DateTimeField(db_index=True)
    JobNo = models.IntegerField(db_index=True)
    RecipeNo = models.IntegerField(db_index=True)
    RecipeName = models.CharField(max_length=255, null=True, blank=True)
    Bitumen_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Filler_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Reclaim_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Temperature_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Bitumen_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Filler_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Reclaim_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Temperature_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin1_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin1_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin2_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin2_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin3_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin3_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin4_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin4_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin5_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin5_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin6_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin6_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin7_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin7_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin8_Actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    HotBin8_Target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'BatchLogs'
        managed = True
        unique_together = ['BatchNo', 'Time', 'JobNo']
        indexes = [
            models.Index(fields=['Time']),
            models.Index(fields=['RecipeName']),
        ]

    def __str__(self):
        return f"BatchLog {self.BatchNo} - {self.Time}"

User = get_user_model()

class ParsingSchedule(models.Model):

    FREQUENCY_CHOICES = [
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ]
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    name = models.CharField(max_length=255)
    ftp_path = models.CharField(max_length=255)

    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='days')
    every = models.PositiveIntegerField(default=1, help_text="Repeat every X [frequency]")

    # For weekly schedules
    week_days = models.CharField(
        max_length=20, 
        blank=True, 
        help_text="Comma-separated days of week (0-6 where 0=Monday)"
    )
    
    # For monthly schedules
    day_of_month = models.PositiveSmallIntegerField(
        null=True, 
        blank=True, 
        help_text="Day of month (1-31)"
    )

    # Time of day to run
    run_time = models.TimeField(default='00:00')

    schedule_cron = models.CharField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9]))$',
                message='Invalid cron format'
            )
        ],
        blank=True
    )
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generate cron expression from simplified fields
        if not self.schedule_cron:
            self.schedule_cron = self.generate_cron()
        super().save(*args, **kwargs)
    
    def generate_cron(self):
        """Convert simplified schedule to cron expression"""
        minute = self.run_time.minute
        hour = self.run_time.hour
        
        if self.frequency == 'minutes':
            return f'*/{self.every} * * * *'
        elif self.frequency == 'hours':
            return f'{minute} */{self.every} * * *'
        elif self.frequency == 'days':
            return f'{minute} {hour} */{self.every} * *'
        elif self.frequency == 'weeks' and self.week_days:
            days = self.week_days.split(',')
            return f'{minute} {hour} * * {",".join(days)}'
        elif self.frequency == 'months' and self.day_of_month:
            return f'{minute} {hour} {self.day_of_month} */{self.every} *'
        return '0 0 * * *' 
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    

class ProcessedFile(models.Model):

    task = models.ForeignKey('ParsingTask', on_delete=models.CASCADE, null=True, related_name='processed_files_rel')

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('skipped', 'Skipped'),
        ('error', 'Error')
    ]
    TRIGGER_SOURCES = [
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled')
    ]
    
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=[('CSV', 'CSV'), ('XML', 'XML')])
    file_path = models.CharField(max_length=255)
    export_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.TextField(null=True, blank=True)
    trigger_source = models.CharField(max_length=20, choices=TRIGGER_SOURCES, default='manual')
    schedule = models.ForeignKey(ParsingSchedule, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-export_time']

    def __str__(self):
        return self.file_name
    

class ParsingTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('interrupted', 'Interrupted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    processed_files_count = models.IntegerField(default=0)
    current_file = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Task {self.id} ({self.status})"
