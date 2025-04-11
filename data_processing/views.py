from django.core.cache import cache
import json
import csv
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from datetime import timedelta, datetime
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, FileResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .tasks import process_xml_files, resume_parsing_task, fetch_energy_data
from .models import BatchLog,ParsingSchedule, ProcessedFile, OEEDailyData, PlantRunTime, DailyMaterials, DailyRecipes, EnergyData
from .forms import BatchLogForm
from decimal import Decimal
from django.core.files.storage import default_storage
from celery.result import AsyncResult
from roadstone_project.celery import app
from django.views.decorators.http import require_GET, require_http_methods
from django.db.models import F, ExpressionWrapper, DecimalField, Sum, Q, FloatField, Avg, Value
from django.db.models.functions import Coalesce, Cast, TruncDate 
from django.db import models
from .tasks import pause_parsing, resume_parsing, scheduled_parse
import logging

# Configure logger  
logger = logging.getLogger(__name__)

class CustomLoginView(View):
    template_name = 'login.html'  

    def get(self, request):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect('/admin/')
            elif hasattr(request.user, 'profile'):
                if request.user.profile.role == 'Manager':
                    return redirect('manager_home')
                elif request.user.profile.role == 'Operator':
                    return redirect('operator_home')
            return redirect('home')
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome, {username}!')
            if user.is_superuser:
                return redirect('/admin/')
            elif hasattr(user, 'profile'):
                if user.profile.role == 'Manager':
                    return redirect('manager_home')
                elif user.profile.role == 'Operator':
                    return redirect('operator_home')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
        return render(request, self.template_name)

# Role-Based Home Views
@login_required
def admin_home(request):
    return HttpResponse("Admin Home Page")


@login_required
def manager_home(request):
    print("Received time_range:", request.GET.get('time_range'))
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'Manager':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    # Default values
    time_range = 30
    labels = []
    values = []
    operational_hours = 0
    utilization_rate = 0
    total_available_hours = 12
    total_production = 0
    rap_consumption = 0
    electricity_consumption = 0
    material_data = []

    # Get time range from request
    if 'time_range' in request.GET:
        try:
            time_range = int(request.GET['time_range'])
        except (ValueError, TypeError):
            pass

    # Filter BatchLog data based on time range
    if time_range > 0:
        cutoff_date = timezone.now() - timedelta(days=time_range)
        batchlogs = BatchLog.objects.filter(Time__gte=cutoff_date)
        energy_data = EnergyData.objects.filter(date__gte=cutoff_date.date())
    else:
        batchlogs = BatchLog.objects.all()
        energy_data = EnergyData.objects.all()

    # Calculate Electricity Consumption
    electricity_aggregate = energy_data.aggregate(
        total=Sum('consumption', output_field=FloatField())
    )
    electricity_consumption = electricity_aggregate.get('total') or 0
    formatted_electricity = "{:,.2f} kWh".format(electricity_consumption)

    # Calculate Total Production
    hotbin_fields = [
        'HotBin1_Actual', 'HotBin2_Actual', 'HotBin3_Actual',
        'HotBin4_Actual', 'HotBin5_Actual', 'HotBin6_Actual',
        'HotBin7_Actual', 'HotBin8_Actual'
    ]
    aggregates = batchlogs.aggregate(
        **{field: Sum(field, output_field=FloatField()) for field in hotbin_fields}
    )
    total_production = sum(
        value if value is not None else 0 for value in aggregates.values()
    )
    formatted_total_production = "{:,.2f}".format(total_production)

    # Calculate RAP Consumption
    rap_aggregate = batchlogs.aggregate(
        total=Sum('Reclaim_Actual', output_field=FloatField())
    )
    rap_consumption = rap_aggregate.get('total') or 0
    formatted_rap_consumption = "{:,.2f}".format(rap_consumption)

    # Fetch Material Consumption Data
    if time_range > 0:
        material_cutoff = cutoff_date.date()  # Use date part for DailyMaterials
        materials = DailyMaterials.objects.filter(date__gte=material_cutoff)
    else:
        materials = DailyMaterials.objects.all()

    materials = materials.order_by('-date')

    material_data = [] #This is the data for the material table on dashboard
    for material in materials:
        date_str = material.date.strftime('%Y-%m-%d') if material.date else 'Unknown Date'
        material_name = material.MaterialName or 'Unknown'
        quantity = material.Quantity if material.Quantity is not None else 0
        formatted_quantity = "{:,.2f}".format(quantity)
        # For each material type in date range, sum consumption
        material_data.append({
            'date': date_str, #Remove Date - just show total for the period
            'MaterialName': material_name,
            'Quantity': formatted_quantity
        })

    # Prepare BatchLog data for chart
    batchlogs = batchlogs.annotate(
        total_tonnage=ExpressionWrapper(
            Coalesce(F('HotBin1_Actual'), 0) + 
            Coalesce(F('HotBin2_Actual'), 0) + 
            Coalesce(F('HotBin3_Actual'), 0) +
            Coalesce(F('HotBin4_Actual'), 0) + 
            Coalesce(F('HotBin5_Actual'), 0) + 
            Coalesce(F('HotBin6_Actual'), 0) +
            Coalesce(F('HotBin7_Actual'), 0) +
            Coalesce(F('HotBin8_Actual'), 0),
            output_field=DecimalField()
        )
    ).values('Time', 'total_tonnage').order_by('Time')

    # Prepare chart data
    if batchlogs.exists():
        labels = [log['Time'].strftime('%Y-%m-%d %H:%M:%S') for log in batchlogs]
        values = [float(log['total_tonnage']) for log in batchlogs]

        previous_time = None
        for log in batchlogs:
            current_time = log['Time']
            if previous_time:
                time_diff = (current_time - previous_time).total_seconds() / 3600
                operational_hours += time_diff
            previous_time = current_time

        if total_available_hours > 0:
            utilization_rate = (operational_hours / total_available_hours) * 100

    utilization_data = {
        'operational_hours': operational_hours,
        'idle_hours': total_available_hours - operational_hours,
        'utilization_rate': utilization_rate
    }

    return render(request, 'manager_home.html', {
        'labels': json.dumps(labels),
        'values': json.dumps(values),
        'utilization_data': json.dumps(utilization_data),
        'time_range': time_range,
        'total_production': formatted_total_production,
        'rap_consumption': formatted_rap_consumption,
        'electricity_consumption': formatted_electricity,
        'material_data': json.dumps(material_data),
    })



@login_required
def operator_home(request):
    print("Received time_range:", request.GET.get('time_range'))
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'Operator':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    # Default values
    time_range = 30
    labels = []
    values = []
    total_production = 0
    rap_consumption = 0
    electricity_consumption = 0
    material_data = []

    # Get time range from request
    if 'time_range' in request.GET:
        try:
            time_range = int(request.GET.get('time_range'))
        except (ValueError, TypeError):
            pass

    # Standardized date filtering
    end_date = timezone.now().date()
    if time_range > 0:
        start_date = end_date - timedelta(days=time_range)
        date_filter = Q(date__gte=start_date) & Q(date__lte=end_date)
        material_cutoff = start_date
    else:
        date_filter = Q()  # All time
        material_cutoff = None

    # Filter data based on time range
    oee_data = OEEDailyData.objects.filter(date_filter)
    energy_data = EnergyData.objects.filter(date_filter)

    # Standardized total production calculation
    production_aggregate = oee_data.aggregate(
        total_combined=Coalesce(
            Sum(F('TotalProduction') + F('TotalEmptyOut')),
            0.0,
            output_field=FloatField()
        )
    )
    total_production = production_aggregate['total_combined']
    formatted_total_production = "{:,.2f}".format(total_production)

    # Calculate Electricity Consumption
    electricity_aggregate = energy_data.aggregate(
        total=Coalesce(Sum('consumption'), 0.0, output_field=FloatField())
    )
    electricity_consumption = electricity_aggregate['total']
    formatted_electricity = "{:,.2f} kWh".format(electricity_consumption)

    # Calculate RAP Consumption
    rap_query = Q(MaterialName='Reclaim Asphalt')
    if material_cutoff:
        rap_query &= Q(date__gte=material_cutoff)
    
    rap_aggregate = DailyMaterials.objects.filter(rap_query).aggregate(
        total=Coalesce(Sum('Quantity'), 0.0, output_field=FloatField())
    )
    rap_consumption = rap_aggregate['total']
    formatted_rap_consumption = "{:,.2f}".format(rap_consumption)

    # Fetch Material Consumption Data
    material_query = Q()
    if material_cutoff:
        material_query = Q(date__gte=material_cutoff)
    
    materials = DailyMaterials.objects.filter(material_query).order_by('-date')

    material_data = []
    for material in materials:
        date_str = material.date.strftime('%Y-%m-%d') if material.date else 'Unknown Date'
        material_data.append({
            'date': date_str,
            'MaterialName': material.MaterialName or 'Unknown',
            'Quantity': "{:,.2f}".format(material.Quantity) if material.Quantity is not None else "0.00"
        })

    # Prepare OEE data for chart
    chart_data = oee_data.annotate(
        daily_production=ExpressionWrapper(
            F('TotalProduction') + F('TotalEmptyOut'),
            output_field=FloatField()
        )
    ).values('date', 'daily_production').order_by('date')

    # Prepare chart data
    if chart_data.exists():
        labels = [entry['date'].strftime('%Y-%m-%d') for entry in chart_data]
        values = [float(entry['daily_production']) for entry in chart_data]

    return render(request, 'operator_home.html', {
        'labels': json.dumps(labels),
        'values': json.dumps(values),
        'time_range': time_range,
        'total_production': formatted_total_production,
        'rap_consumption': formatted_rap_consumption,
        'electricity_consumption': formatted_electricity,
        'material_data': json.dumps(material_data),
    })

@login_required
def custom_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

@login_required
def home(request):
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'Admin':
            return redirect('/admin/')
        elif request.user.profile.role == 'Manager':
            return redirect('manager_home')
        elif request.user.profile.role == 'Operator':
            return redirect('operator_home')
    else:
        messages.error(request, 'User profile not found. Please contact support.')
        return redirect('login')
    
@login_required
def oee_dashboard(request):
    """Render the OEE dashboard template"""
    return render(request, 'oee_dashboard.html')

@login_required
def oee_dashboard_api(request):
    """API endpoint for OEE dashboard with complete time range support"""
    try:
        days = int(request.GET.get('days', 30))
        end_date = timezone.now().date()
        
        # Handle "All Time" case
        if days == 0:
            start_date = None
        else:
            start_date = end_date - timedelta(days=days)

        # Base filter for date-based models
        date_filter = Q()
        if start_date:
            date_filter = Q(date__gte=start_date) & Q(date__lte=end_date)
            

        # 1. Get OEEDailyData
        oee_data = OEEDailyData.objects.filter(date_filter).aggregate(
            total_production=Coalesce(Sum('TotalProduction', output_field=FloatField()), 0.0),
            total_emptyout=Coalesce(Sum('TotalEmptyOut', output_field=FloatField()), 0.0)
        ) # OEEDailyData_TotalProduction + OEEDailyData_TotalEmptyOut

        # 2. Get Plant Runtime Data
        runtime_fields = [
            'MixingActive', 'Mixer', 'Screen', 'HotElevator', 'Dryer',
            'BurnerFlameOn', 'SlingerForward', 'SlingerReverse',
            'CollectConveyor', 'DustBlower', 'DustBlowerRotaryValve'
        ]
        runtime_data = PlantRunTime.objects.filter(date_filter).aggregate(
            **{field: Sum(field) for field in runtime_fields}
        )

        # 3. Get Materials Data
        material_data = DailyMaterials.objects.filter(date_filter).aggregate(
            total_materials=Coalesce(Sum('Quantity', output_field=FloatField()), 0.0)
        )

        # 4. Get RAP and Bitumen from BatchLog
        batch_filter = Q()
        if start_date:
            batch_filter = Q(Time__date__gte=start_date) & Q(Time__date__lte=end_date)
            
        rap_bitumen = BatchLog.objects.filter(batch_filter).aggregate(
            total_rap=Coalesce(Sum('Reclaim_Actual', output_field=FloatField())/1000, 0.0),
            total_bitumen=Coalesce(Sum('Bitumen_Actual', output_field=FloatField())/1000, 0.0)
        )

        # 5. Get Electricity Consumption
        electricity_data = EnergyData.objects.filter(date_filter).aggregate(
            total_consumption=Coalesce(Sum('consumption', output_field=FloatField()), 0.0)
        )

        # 5. Calculate Mixer Hours
        total_mixer_seconds = runtime_data.get('Mixer', 0) or 0
        total_mixer_hours = total_mixer_seconds / 3600 if total_mixer_seconds else 0

        # 6. Prepare response
        response_data = {
            'total_production': float(oee_data['total_production']),
            'total_emptyout': float(oee_data['total_emptyout']),
            'total_consumption': float(electricity_data['total_consumption']),
            'total_consumption': float(electricity_data['total_consumption']),
            'runtime_data': {k: float(v or 0) for k, v in runtime_data.items()},
            'drying_efficiency': {
                'avg_drying_rate': 0.0,
                'total_materials': float(material_data['total_materials']),
                'total_rap': float(rap_bitumen['total_rap']),
                'total_bitumen': float(rap_bitumen['total_bitumen']),
                'total_mixer_hours': float(total_mixer_hours)
            }
        }

        # Calculate average drying rate safely
        if total_mixer_hours > 0:
            numerator = (response_data['drying_efficiency']['total_materials'] 
                        - response_data['drying_efficiency']['total_rap'] 
                        - response_data['drying_efficiency']['total_bitumen'])
            response_data['drying_efficiency']['avg_drying_rate'] = round(
                numerator / total_mixer_hours, 2
            )

        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def production_dashboard(request):
    # Get parameters from request
    time_range = int(request.GET.get('time_range', 30))
    selected_recipe = request.GET.get('recipe', '').strip()
    unit = request.GET.get('unit', 't')

    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=time_range) if time_range > 0 else None

    # Base queries
    daily_recipes = DailyRecipes.objects.all()
    batch_logs = BatchLog.objects.all()
    rap_materials = DailyMaterials.objects.filter(MaterialName='Reclaim Asphalt')
    
    # Apply date filters
    if start_date:
        daily_recipes = daily_recipes.filter(date__gte=start_date.date(), date__lte=end_date.date())
        batch_logs = batch_logs.filter(Time__gte=start_date, Time__lte=end_date)
        rap_materials = rap_materials.filter(date__gte=start_date.date(), date__lte=end_date.date())

    # Get available recipes from DailyRecipes
    recipe_names = daily_recipes.exclude(RecipeName__isnull=True)\
                              .order_by('RecipeName')\
                              .values_list('RecipeName', flat=True)\
                              .distinct()
    
    # Apply recipe filter
    if selected_recipe:
        daily_recipes = daily_recipes.filter(RecipeName=selected_recipe)
        batch_logs = batch_logs.filter(RecipeName=selected_recipe)
        # Note: DailyMaterials typically doesn't have RecipeName, so it don't filter it but the date range is possible

    # Production calculation from DailyRecipes
    production_expression = ExpressionWrapper(
        Coalesce(F('Total'), Value(0.0)),
        output_field=FloatField()
    )

    # Aggregate metrics
    production_metrics = daily_recipes.aggregate(
        total_production=Coalesce(Sum(production_expression, output_field=FloatField()), 0.0)
    )

    # Get RAP consumption from DailyMaterials
    rap_metrics = rap_materials.aggregate(
        total_reclaim=Coalesce(Sum('Quantity', output_field=FloatField()), 0.0)
    )

    bitumen_metrics = batch_logs.aggregate(
        total_bitumen=Coalesce(Sum('Bitumen_Actual', output_field=FloatField()), 0.0)
    )

    temp_metrics = batch_logs.aggregate(
        avg_temp_target=Coalesce(Avg('Temperature_Target', output_field=FloatField()), 0.0),
        avg_temp_actual=Coalesce(Avg('Temperature_Actual', output_field=FloatField()), 0.0)
    )

    # Convert values based on selected unit
    conversion_factor = 1000 if unit == 'kt' else 1
    total_prod = float(production_metrics['total_production']) / conversion_factor
    total_reclaim = float(rap_metrics['total_reclaim']) / conversion_factor
    total_bitumen = float(bitumen_metrics['total_bitumen']) / 1000 / conversion_factor  # Convert from kg to tons
    
    # Calculate percentages - now using RAP from DailyMaterials
    rap_percent = (float(rap_metrics['total_reclaim']) / float(production_metrics['total_production']) * 100) if float(production_metrics['total_production']) > 0 else 0
    bitumen_percent = (float(bitumen_metrics['total_bitumen']) / 1000 / float(production_metrics['total_production']) * 100) if float(production_metrics['total_production']) > 0 else 0
    aggregates_percent = (100 - rap_percent - bitumen_percent) if float(production_metrics['total_production']) > 0 else 0

    # Temperature metrics
    avg_temp_target = float(temp_metrics['avg_temp_target'])
    avg_temp_actual = float(temp_metrics['avg_temp_actual'])
    temp_deviation = avg_temp_actual - avg_temp_target  

    # Chart data
    chart_data = daily_recipes.values('date').annotate(
        daily_total=ExpressionWrapper(
            Coalesce(Sum(production_expression, output_field=FloatField()), 0.0) / conversion_factor,
            output_field=FloatField()
        )
    ).order_by('date')

    # Prepare context
    context = {
        # Filter parameters
        'time_range': time_range,
        'selected_recipe': selected_recipe,
        'unit': unit,
        'recipe_names': recipe_names,
        
        # Production metrics
        'total_production': f"{total_prod:,.2f} {unit}",
        'rap_percentage': f"{rap_percent:.2f}%",
        'bitumen_percentage': f"{bitumen_percent:.2f}%",
        'aggregates_percentage': f"{aggregates_percent:.2f}%",
        
        # Temperature metrics
        'avg_temp_target': f"{avg_temp_target:.1f}°C",
        'avg_temp_actual': f"{avg_temp_actual:.1f}°C",
        'temp_deviation': f"{temp_deviation:.1f}°C",
        
        # Chart data
        'chart_labels': [item['date'].isoformat() for item in chart_data],
        'chart_data': [float(item['daily_total']) for item in chart_data],
        'has_data': daily_recipes.exists(),
        
        # For JavaScript
        'unit_json': json.dumps(unit),
        'time_range_json': json.dumps(time_range),
        'selected_recipe_json': json.dumps(selected_recipe)
    }
    
    return render(request, 'production.html', context)




@login_required
def upload_xml(request):

    
    processed_files = ProcessedFile.objects.all().order_by('-export_time')
    
    # Get parsing state
    parsing_active = cache.get('parsing_active', False)
    pause_parsing = cache.get('pause_parsing', False)
    
    active_schedules = ParsingSchedule.objects.filter(is_active=True)
    return render(request, 'upload_xml.html', {
        'processed_files': processed_files,
        'parsing_active': parsing_active,
        'pause_parsing': pause_parsing,
        'active_schedules': active_schedules,
    })  


@require_http_methods(["POST"])
@login_required
def trigger_parsing(request):
    """Handle both manual and scheduled parsing triggers"""
    response_data = {
        'status': 'error',
        'message': '',
        'task_id': None,
        'type': None
    }

    try:
        # Auto-cancel previous task
        old_task_id = cache.get('current_parsing_task')
        if old_task_id:
            try:
                app.control.revoke(old_task_id, terminate=True)
                logger.info(f"Cancelled previous task: {old_task_id}")
            except Exception as revoke_error:
                logger.error(f"Failed to cancel task {old_task_id}: {str(revoke_error)}")
                # Non-critical error, continue execution

        schedule_id = request.GET.get('schedule_id')
        
        if schedule_id:
            # Scheduled parsing
            if not request.user.is_superuser:
                response_data['message'] = 'Permission denied'
                return JsonResponse(response_data, status=403)
                
            try:
                task = scheduled_parse.delay(schedule_id)
                if not task.id:
                    raise ValueError("Task ID not generated")
                
                cache.set('current_parsing_task', task.id, timeout=None)
                response_data.update({
                    'status': 'started',
                    'task_id': task.id,
                    'type': 'scheduled',
                    'message': 'Scheduled parsing started'
                })
                return JsonResponse(response_data)
                
            except Exception as schedule_error:
                logger.error(f"Scheduled parse failed: {str(schedule_error)}", exc_info=True)
                response_data['message'] = 'Failed to start scheduled parsing'
                return JsonResponse(response_data, status=500)

        # Manual parsing
        try:
            cache.set('pause_parsing', False, timeout=None)
            task = process_xml_files.delay()
            if not task.id:
                raise ValueError("Task ID not generated")
            
            cache.set('current_parsing_task', task.id, timeout=None)
            response_data.update({
                'status': 'started',
                'task_id': task.id,
                'type': 'manual',
                'message': 'Manual parsing started'
            })
            return JsonResponse(response_data)
            
        except Exception as manual_error:
            logger.error(f"Manual parse failed: {str(manual_error)}", exc_info=True)
            response_data['message'] = 'Failed to start manual parsing'
            return JsonResponse(response_data, status=500)

    except Exception as e:
        logger.error(f"Unexpected error in trigger_parsing: {str(e)}", exc_info=True)
        response_data['message'] = 'Internal server error'
        return JsonResponse(response_data, status=500)
    
    

@csrf_exempt
def check_interrupted(request):
    """Check for tasks that can be resumed"""
    last_interrupted = ProcessedFile.objects.filter(
        status='interrupted'
    ).order_by('-export_time').first()
    
    if last_interrupted:
        return JsonResponse({
            'found': True,
            'task_id': last_interrupted.task.id,
            'last_file': last_interrupted.file_name,
            'progress': int((last_interrupted.task.processed_files / last_interrupted.task.total_files) * 100)
        })
    return JsonResponse({'found': False})    


@require_http_methods(["POST"])
@login_required
def toggle_parsing(request):
    """Toggle pause/resume state"""
    try:
        if cache.get('pause_parsing', False):
            resume_parsing.delay()
            return JsonResponse({'status': 'resumed'})
        else:
            pause_parsing.delay()
            return JsonResponse({'status': 'paused'})
    except Exception as e:
        logger.error(f"Toggle parsing failed: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@csrf_exempt
@require_http_methods(["POST"])
def pause_parsing_view(request):  # Bagong pangalan
    """Pause current task"""
    logger.info(f"Pause request received from {request.user}")
    pause_parsing.delay()  # Tawagin ang Celery task
    return JsonResponse({'status': 'paused'})


@require_http_methods(["GET"])
@login_required
def get_parsing_state(request):
    """Get current parsing state including schedule info"""
    current_task_id = cache.get('current_parsing_task')
    task_data = {
        'is_active': bool(current_task_id),
        'is_paused': cache.get('pause_parsing', False),
        'current_task': current_task_id,
        'schedules': []
    }
    
    if request.user.is_superuser:
        task_data['schedules'] = list(
            ParsingSchedule.objects.filter(is_active=True).values(
                'id', 'name', 'schedule_cron', 'ftp_path'
            )
        )
    
    if current_task_id:
        task = AsyncResult(current_task_id)
        task_data.update({
            'task_state': task.state,
            'task_result': task.result if task.ready() else None
        })
    
    return JsonResponse(task_data)

@csrf_exempt
def task_state(request, task_id):
    """Get detailed state of a task"""
    task = AsyncResult(task_id)
    processed = ProcessedFile.objects.filter(task_id=task_id, status='success').count()
    total = getattr(task, 'total_files', 0)
    
    return JsonResponse({
        'state': task.state,
        'progress': int((processed / total) * 100) if total else 0,
        'last_file': getattr(task, 'current_file', ''),
        'processed_files': processed,
        'total_files': total
    })

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_schedule(request):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    try:
        schedule = ParsingSchedule.objects.create(
            name=request.POST.get('name'),
            ftp_path=request.POST.get('ftp_path'),
            schedule_cron=request.POST.get('schedule_cron'),
            created_by=request.user
        )
        return JsonResponse({'status': 'success', 'schedule_id': schedule.id})
    except Exception as e:
        logger.error(f"Schedule creation failed: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
@csrf_exempt
@require_http_methods(["POST"])
@login_required
def toggle_schedule(request, schedule_id):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    try:
        schedule = ParsingSchedule.objects.get(id=schedule_id)
        schedule.is_active = not schedule.is_active
        schedule.save()
        return JsonResponse({'status': 'success', 'is_active': schedule.is_active})
    except Exception as e:
        logger.error(f"Schedule toggle failed: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def celery_progress(request, task_id):
    task = AsyncResult(task_id)
    
    response = {
        'state': task.state,
        'complete': task.ready(),
    }
    
    if task.state == 'FAILURE':
        # Safe to get an error message
        try:
            error = str(task.result)
        except Exception as e:
            error = f"Unknown error: {repr(task.result)}"
        response.update({
            'status': error,
            'error_type': task.result.__class__.__name__ if task.result else None
        })
    else:
        # Add the safety check
        progress_info = task.info or {}
        response.update({
            'progress': progress_info.get('progress', 0),
            'description': progress_info.get('description', ''),
            'current_file': progress_info.get('current_file', ''),
            'processed_files': progress_info.get('processed_files', 0),
            'total_files': progress_info.get('total_files', 0),
        })
    
    return JsonResponse(response)

@require_http_methods(["GET"])
@login_required
def get_processed_files(request):
    """Enhanced file listing with schedule info"""
    files = ProcessedFile.objects.select_related('schedule').order_by('-export_time')
    
    file_data = []
    for file in files:
        file_data.append({
            'file_name': file.file_name,
            'file_type': file.file_type,
            'status': file.status,
            'export_time': file.export_time.strftime('%Y-%m-%d %H:%M:%S'),
            'trigger_source': file.trigger_source,
            'schedule': file.schedule.name if file.schedule else None,
            'error': file.error_message
        })
    
    return JsonResponse({'files': file_data})


@login_required
def processed_files_log(request):
    processed_files = ProcessedFile.objects.all().order_by('-export_time')
    context = {
        'processed_files': processed_files,
    }
    return render(request, 'processed_files_log.html', context)


@login_required
def trigger_energy_fetch(request):
    """Trigger API fetching manually"""
    task = fetch_energy_data.delay()
    return JsonResponse({
        "status": "started",
        "task_id": task.id,
        "message": "Energy data fetch initiated"
    })

@login_required
def fetch_energy_data_page(request):
    daily_data = EnergyData.objects.values('date', 'meter_name').annotate(
        total_consumption=Sum('consumption')
    ).order_by('-date')
    
    return render(request, 'fetch_energy_data.html', {
        'daily_data': daily_data
    })

@login_required
def fetch_energy_data_page(request):
    """Render the fetching page"""
    latest_data = EnergyData.objects.order_by('-timestamp')[:50]
    return render(request, 'fetch_energy_data.html', {
        'energy_data': latest_data
    })



@login_required
def batchlog_list(request):
    if request.method == 'POST' and 'edit' in request.POST:
        batch_no = request.POST.get('batchlog_id')
        batchlog = get_object_or_404(BatchLog, BatchNo=batch_no)
        form = BatchLogForm(request.POST, instance=batchlog)
        if form.is_valid():
            form.save()
            messages.success(request, 'BatchLog updated successfully!')
            return redirect('batchlog_list')

    elif request.method == 'POST' and 'delete' in request.POST:
        batch_no = request.POST.get('batchlog_id')
        batchlog = get_object_or_404(BatchLog, BatchNo=batch_no)
        batchlog.delete()
        messages.success(request, 'BatchLog deleted successfully!')
        return redirect('batchlog_list')

    batchlogs = BatchLog.objects.all().order_by('-Time')
    return render(request, 'batchlog_list.html', {'batchlogs': batchlogs})

@login_required
def raw_data_ajax(request):
    try:

        # Handle CSV Export
        if request.GET.get('export_csv'):
            from_date = request.GET.get('date_start', '')
            to_date = request.GET.get('date_end', '')
            
            # Format the date range for filename
            date_range = ""
            if from_date and to_date:
                from_formatted = datetime.strptime(from_date, '%Y-%m-%d').strftime('%d%b%Y').upper()
                to_formatted = datetime.strptime(to_date, '%Y-%m-%d').strftime('%d%b%Y').upper()
                date_range = f"{from_formatted}-{to_formatted}"
            elif from_date:
                date_range = datetime.strptime(from_date, '%Y-%m-%d').strftime('%d%b%Y').upper() + "-CURRENT"
            elif to_date:
                date_range = "START-" + datetime.strptime(to_date, '%Y-%m-%d').strftime('%d%b%Y').upper()
            else:
                date_range = "ALL-DATES"
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="BatchLog_{date_range}.csv"'
            
            writer = csv.writer(response)
            
            # Write headers
            writer.writerow([
                'ID', 'Date', 'Time', 'Batch No', 'Job No', 'Recipe No', 'Recipe Name',
                'Bitumen Actual', 'Filler Actual', 'Reclaim Actual', 'Temperature Actual',
                'HotBin 1 Actual', 'HotBin 2 Actual','HotBin 3 Actual', 'HotBin 4 Actual',
                'HotBin 5 Actual', 'HotBin 6 Actual', 'HotBin 7 Actual', 'HotBin 8 Actual',
                'Bitumen Target', 'Filler Target', 'Reclaim Target', 'Temperature Target',
                'HotBin 1 Target', 'HotBin 2 Target', 'HotBin 3 Target', 'HotBin 4 Target',
                'HotBin 5 Target', 'HotBin 6 Target', 'HotBin 7 Target', 'HotBin 8 Target',
            ])
            
            # Apply the same filters as the table
            queryset = BatchLog.objects.all()
            
            if request.GET.get('date_start'):
                queryset = queryset.filter(Time__date__gte=request.GET['date_start'])
            if request.GET.get('date_end'):
                queryset = queryset.filter(Time__date__lte=request.GET['date_end'])
            if request.GET.get('recipe'):
                queryset = queryset.filter(RecipeName=request.GET['recipe'])
            
            # Write data rows
            for item in queryset:
                writer.writerow([
                    item.id,
                    item.Time.strftime('%Y-%m-%d') if item.Time else '',
                    item.Time.strftime('%H:%M:%S') if item.Time else '',
                    item.BatchNo,
                    item.JobNo,
                    item.RecipeNo,
                    item.RecipeName,
                    item.Bitumen_Actual,
                    item.Filler_Actual,
                    item.Reclaim_Actual,
                    item.Temperature_Actual,
                    item.HotBin1_Actual,
                    item.HotBin2_Actual,
                    item.HotBin3_Actual,
                    item.HotBin4_Actual,
                    item.HotBin5_Actual,    
                    item.HotBin6_Actual,
                    item.HotBin7_Actual,
                    item.HotBin8_Actual,
                    item.Bitumen_Target,
                    item.Filler_Target,
                    item.Reclaim_Target,
                    item.Temperature_Target,
                    item.HotBin1_Target,
                    item.HotBin2_Target,
                    item.HotBin3_Target,
                    item.HotBin4_Target,
                    item.HotBin5_Target,
                    item.HotBin6_Target,
                    item.HotBin7_Target,
                    item.HotBin8_Target
                ])
            
            return response

        # Get filters from request
        date_start = request.GET.get('date_start')
        date_end = request.GET.get('date_end')
        recipe_name = request.GET.get('recipe')
        
        # Handle recipe list request
        if request.GET.get('get_recipes'):
            recipes = BatchLog.objects.exclude(RecipeName__isnull=True)\
                                    .order_by('RecipeName')\
                                    .values_list('RecipeName', flat=True)\
                                    .distinct()
            return JsonResponse({'recipes': list(recipes)})

        # Base queryset
        queryset = BatchLog.objects.all()

        # Apply date filters
        if date_start:
            queryset = queryset.filter(Time__date__gte=date_start)
        if date_end:
            queryset = queryset.filter(Time__date__lte=date_end)
        
        # Apply recipe filter
        if recipe_name:
            queryset = queryset.filter(RecipeName=recipe_name)

        # Get DataTables parameters
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '')

        # Apply search
        if search_value:
            queryset = queryset.filter(
                Q(BatchNo__icontains=search_value) |
                Q(JobNo__icontains=search_value) |
                Q(RecipeNo__icontains=search_value) |
                Q(RecipeName__icontains=search_value)
            )

        # Total records count (before filtering)
        total_records = BatchLog.objects.count()
        
        # Filtered count (after all filters)
        filtered_records = queryset.count()

        # Ordering
        order_col = int(request.GET.get('order[0][column]', 1))
        order_dir = request.GET.get('order[0][dir]', 'desc')
        order_field = request.GET.get(f'columns[{order_col}][data]', 'Time')
        
        # Map DataTables columns to model fields
        field_mapping = {
            'Date': 'Time',
            'Time': 'Time',
            'DateTime': 'Time',
            'BatchNo': 'BatchNo',
            'JobNo': 'JobNo',
            'RecipeNo': 'RecipeNo',
            'RecipeName': 'RecipeName'
        }
        order_field = field_mapping.get(order_field, order_field)
        
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        queryset = queryset.order_by(order_field)

        # Pagination
        queryset = queryset[start:start + length]

        # Prepare response data
        data = []
        for i, item in enumerate(queryset, start=start + 1):
            data.append({
                "id": i,
                "Date": item.Time.strftime('%Y-%m-%d') if item.Time else '',
                "Time": item.Time.strftime('%H:%M:%S') if item.Time else '',
                "DateTime": item.Time.isoformat() if item.Time else '',
                "BatchNo": item.BatchNo,
                "JobNo": item.JobNo,
                "RecipeNo": item.RecipeNo,
                "RecipeName": item.RecipeName,
                "Bitumen_Actual": item.Bitumen_Actual,
                "Filler_Actual": item.Filler_Actual,
                "Reclaim_Actual": item.Reclaim_Actual,
                "Temperature_Actual": item.Temperature_Actual,
                "HotBin1_Actual": item.HotBin1_Actual,
                "HotBin2_Actual": item.HotBin2_Actual,
                "HotBin3_Actual": item.HotBin3_Actual,
                "HotBin4_Actual": item.HotBin4_Actual,
                "HotBin5_Actual": item.HotBin5_Actual,
                "HotBin6_Actual": item.HotBin6_Actual,
                "HotBin7_Actual": item.HotBin7_Actual,
                "HotBin8_Actual": item.HotBin8_Actual,
                "Bitumen_Target": item.Bitumen_Target,
                "Filler_Target": item.Filler_Target,
                "Reclaim_Target": item.Reclaim_Target,
                "Temperature_Target": item.Temperature_Target,
                "HotBin1_Target": item.HotBin1_Target,
                "HotBin2_Target": item.HotBin2_Target,
                "HotBin3_Target": item.HotBin3_Target,
                "HotBin4_Target": item.HotBin4_Target,
                "HotBin5_Target": item.HotBin5_Target,
                "HotBin6_Target": item.HotBin6_Target,
                "HotBin7_Target": item.HotBin7_Target,
                "HotBin8_Target": item.HotBin8_Target
            })
        
        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data
        })

    except Exception as e:
        logger.error(f"Error in raw_data_ajax: {str(e)}")
        if request.GET.get('export_csv'):
            return HttpResponse("Error generating CSV: " + str(e), status=500)
        return JsonResponse({
            "draw": 0,
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(e)
        }, status=500)