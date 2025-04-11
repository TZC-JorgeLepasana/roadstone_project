from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Profile, BatchLog, ProcessedFile,ParsingSchedule, ParsingTask

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role')
    list_select_related = ('profile',)

    def get_role(self, instance):
        return instance.profile.role
    get_role.short_description = 'Role'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(BatchLog)
class BatchLogAdmin(admin.ModelAdmin):
    list_display = (
        'BatchNo', 'JobNo', 'RecipeNo', 'RecipeName', 'Bitumen_Actual', 'Filler_Actual', 'Reclaim_Actual',
        'Temperature_Actual', 'Bitumen_Target', 'Filler_Target', 'Reclaim_Target', 'Temperature_Target',
        'HotBin1_Actual', 'HotBin1_Target', 'HotBin2_Actual', 'HotBin2_Target', 'HotBin3_Actual', 'HotBin3_Target',
        'HotBin4_Actual', 'HotBin4_Target', 'HotBin5_Actual', 'HotBin5_Target', 'HotBin6_Actual', 'HotBin6_Target',
        'HotBin7_Actual', 'HotBin7_Target', 'HotBin8_Actual', 'HotBin8_Target', 'Time'
    )

    list_editable = (
        'JobNo', 'RecipeNo', 'RecipeName', 'Bitumen_Actual', 'Filler_Actual', 'Reclaim_Actual',
        'Temperature_Actual', 'Bitumen_Target', 'Filler_Target', 'Reclaim_Target', 'Temperature_Target',
        'HotBin1_Actual', 'HotBin1_Target', 'HotBin2_Actual', 'HotBin2_Target', 'HotBin3_Actual', 'HotBin3_Target',
        'HotBin4_Actual', 'HotBin4_Target', 'HotBin5_Actual', 'HotBin5_Target', 'HotBin6_Actual', 'HotBin6_Target',
        'HotBin7_Actual', 'HotBin7_Target', 'HotBin8_Actual', 'HotBin8_Target'
    )

    search_fields = ('BatchNo', 'RecipeName', 'Time')

    list_filter = ('RecipeNo', 'Time')

    ordering = ('BatchNo', 'Time', 'JobNo')

    fieldsets = (
        (None, {
            'fields': ('BatchNo', 'JobNo', 'RecipeNo', 'RecipeName')
        }),
        ('Bitumen, Filler, and Reclaim', {
            'fields': (
                'Bitumen_Actual', 'Bitumen_Target', 'Filler_Actual', 'Filler_Target', 'Reclaim_Actual', 'Reclaim_Target'
            )
        }),
        ('Temperature', {
            'fields': ('Temperature_Actual', 'Temperature_Target')
        }),
        ('HotBin Data', {
            'fields': (
                'HotBin1_Actual', 'HotBin1_Target', 'HotBin2_Actual', 'HotBin2_Target', 'HotBin3_Actual', 'HotBin3_Target',
                'HotBin4_Actual', 'HotBin4_Target', 'HotBin5_Actual', 'HotBin5_Target', 'HotBin6_Actual', 'HotBin6_Target',
                'HotBin7_Actual', 'HotBin7_Target', 'HotBin8_Actual', 'HotBin8_Target'
            )
        }),
        ('Time', {
            'fields': ('Time',)
        }),
    )

@admin.register(ProcessedFile)
class ProcessedFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'get_file_type', 'status', 'export_time', 'trigger_source')
    list_filter = ('status', 'file_type', 'trigger_source', 'export_time')
    search_fields = ('file_name',)
    date_hierarchy = 'export_time'
    
    def get_file_type(self, obj):
        return obj.file_type
    get_file_type.short_description = 'File Type'

@admin.register(ParsingSchedule)
class ParsingScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_schedule_description', 'is_active', 'created_by')
    list_editable = ('is_active',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'ftp_path', 'is_active', 'created_by')
        }),
        ('Scheduling Options', {
            'fields': (
                'frequency',
                'every',
                'week_days',
                'day_of_month',
                'run_time',
                'schedule_cron'
            ),
            'description': """
                <h3>Schedule Configuration</h3>
                <p>Configure how often the parsing should run:</p>
                <ul>
                    <li><strong>Minutes/Hours:</strong> Run every X minutes/hours</li>
                    <li><strong>Days:</strong> Run every X days at specified time</li>
                    <li><strong>Weeks:</strong> Run on specific weekdays</li>
                    <li><strong>Months:</strong> Run on specific day of month</li>
                </ul>
            """
        }),
    )
    readonly_fields = ('schedule_cron',)
    filter_horizontal = ()
    
    def get_schedule_description(self, obj):
        if obj.frequency == 'minutes':
            return f"Every {obj.every} minute(s)"
        elif obj.frequency == 'hours':
            return f"Every {obj.every} hour(s) at :{obj.run_time.minute:02d}"
        elif obj.frequency == 'days':
            return f"Every {obj.every} day(s) at {obj.run_time.strftime('%H:%M')}"
        elif obj.frequency == 'weeks':
            days = [ParsingSchedule.WEEKDAY_CHOICES[int(d)][1] for d in obj.week_days.split(',') if d]
            return f"Weekly on {', '.join(days)} at {obj.run_time.strftime('%H:%M')}"
        elif obj.frequency == 'months':
            return f"Monthly on day {obj.day_of_month} at {obj.run_time.strftime('%H:%M')}"
        return "Custom schedule"
    get_schedule_description.short_description = 'Schedule'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make week_days and day_of_month fields conditionally required
        form.base_fields['week_days'].required = False
        form.base_fields['day_of_month'].required = False
        return form
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only set created_by for new objects
            obj.created_by = request.user
        obj.save()

    class Media:
        css = {
            'all': ('css/admin.css',)
        }
        js = ('js/admin/schedule.js',)    

        

@admin.register(ParsingTask)
class ParsingTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'progress', 'current_file', 'created_at', 'last_updated')
    list_filter = ('status', 'created_at', 'last_updated')
    search_fields = ('id', 'current_file')
    readonly_fields = ('id', 'created_at', 'last_updated', 'progress')
    fieldsets = (
        (None, {
            'fields': ('id', 'status', 'created_at', 'last_updated')
        }),
        ('Progress', {
            'fields': ('total_files', 'processed_files', 'progress', 'current_file'),
            'classes': ('collapse',)
        }),
    )
    
    def progress(self, obj):
        if obj.total_files > 0:
            return f"{obj.processed_files}/{obj.total_files} ({(obj.processed_files/obj.total_files)*100:.1f}%)"
        return "0/0 (0%)"
    progress.short_description = 'Progress'