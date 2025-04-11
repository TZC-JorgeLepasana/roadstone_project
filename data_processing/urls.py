from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views
from .views import (
    home,
    CustomLoginView,
    upload_xml,
    get_processed_files,
    production_dashboard,
    processed_files_log,
    batchlog_list,
    raw_data_ajax,
    admin_home,
    manager_home,
    oee_dashboard_api,
    oee_dashboard,
    # get_production_data,
    # batch_deviations,
    operator_home,
    custom_logout,
    trigger_parsing,
    toggle_parsing,
    get_parsing_state,
    create_schedule,
    toggle_schedule,
    check_interrupted,
    pause_parsing_view,
    resume_parsing,
    task_state,
    pause_parsing,
    fetch_energy_data_page,
    trigger_energy_fetch,
)

urlpatterns = [
    # Authentication routes
    path('', home, name='home'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),

    # XML Processing routes
    path('upload-xml/', login_required(upload_xml), name='upload_xml'),
    path('api/trigger-parsing/', login_required(trigger_parsing), name='trigger_parsing'),
    path('api/toggle-parsing/', login_required(toggle_parsing), name='toggle_parsing'),
    path('api/get-parsing-state/', login_required(get_parsing_state), name='get_parsing_state'),

    path('api/check-interrupted/', check_interrupted, name='check_interrupted'),
    path('api/resume-parsing/', resume_parsing, name='resume_parsing'),
    path('api/task-state/<str:task_id>/', task_state, name='task_state'),
    path('api/pause-parsing/', pause_parsing_view, name='pause_parsing'),


    path('energy/', fetch_energy_data_page, name='energy_fetch'),
    path('trigger-energy-fetch/', trigger_energy_fetch, name='trigger_energy_fetch'),

    # Data endpoints (API)
    path('api/get-processed-files/', login_required(get_processed_files), name='get_processed_files'),
    # path('api/get-production-data/', login_required(get_production_data), name='get_production_data'),
    # path('api/batch-deviations/', login_required(batch_deviations), name='batch_deviations'),

    # Logs and management
    path('oee/', oee_dashboard, name='oee'),
    path('api/oee/', oee_dashboard_api, name='oee_api'),
    path('production/', views.production_dashboard, name='production_dashboard'),
    path('production/', login_required(production_dashboard), name='production'),
    path('processed-files/', login_required(processed_files_log), name='processed_files_log'),
    # path('export-batchlog-csv/', views.export_batchlog_csv, name='export_batchlog_csv'),
    path('raw_data_ajax/', views.raw_data_ajax, name='raw_data_ajax'),
    path('batchlogs/', views.batchlog_list, name='batchlog_list'),

    # Schedule API endpoints (keep these if you're using them)
    path('api/schedules/<int:schedule_id>/toggle/', login_required(toggle_schedule), name='toggle_schedule'),
    path('api/schedules/create/', login_required(create_schedule), name='create_schedule'),

    # Role-based homepages
    path('admin/', admin_home, name='admin_home'),
    path('manager/', manager_home, name='manager_home'),
    path('operator/', operator_home, name='operator_home'),
]


"""

All of the following are for the "Manager" roles:

- Home [Currently Dashboard]
    - Widgetst as currently laid out
    - Production Line chart as currently laid out
    - Replace donut chart with a table listing consumption by material name for the period
- OEE
    - New page on left menu
    - Allow users to pick last 7 days - 30 days etc
        - all data should relate to specified time period
    - Widgets across the top of the page
        - Total Production (Model: OEEDailyData)
        - Total EMptyout (Model: OEEDailyData)
        - Total Electricity Use (sum of the tree electricity meters from PM API)
        - Total Fuel Use (We dont have this yet)
    - Chart area - Donut or pie chart - Split the page 75%/25%
        - Total of all fields from the PlantRunTImeModel (excluding id and date)
        - Table to right showing:
            - Average drying t/hr (sum of daily materials less RAP less bitumen/ sum of mixer)
- Production
    - New page on left menu
    - Allow users to pick last 7 days - 30 days etc
        - all data should relate to specified time period
        - users should be able to pick from the mix recipes produced in the specified time period

    - Widgets
        - Total production of specified mix across specified time period  
        - % RAP (RAP tonnes/Total production tonnes)
        - % Bitumen (Bitumen tonnes/Total production tonnes)
        - % Aggregates (Aggregates tonnes/Total production tonnes)
        - Temperature deviation (Target Temperature||Average of actual temperature)
    - Chart area
        - line graph - like the home page but for just the selected recipe
    
- Batch Detail [Currently Database]
    - The current database tab with the folowing functionality:
        - split out date and time stamps
        - allow users to specify:
            - from date - to date
            - filter what mixes to include in table
            - export to csv



"""