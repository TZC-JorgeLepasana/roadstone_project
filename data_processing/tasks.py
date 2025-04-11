import os
import gc
import pytz
import requests
import logging
from io import BytesIO
import time
import xml.etree.ElementTree as ET
from ftplib import FTP
from decimal import Decimal, InvalidOperation
from celery import shared_task, current_task
from django.conf import settings
from django.utils import timezone
import socket
from datetime import timedelta, datetime
from django.db import transaction
from roadstone_project.settings import CACHE_LOCK_TIMEOUT
from .models import (
    ProcessedFile,
    BatchLog,
    ParsingSchedule,
    OEEDailyData,        # <- Add new models
    PlantRunTime,
    DailyRecipes,
    DailyMaterials,
    EnergyData,
)
from django.core.cache import cache
from celery.exceptions import Ignore, SoftTimeLimitExceeded
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from dateutil import parser

logger = logging.getLogger(__name__)
dublin_tz = pytz.timezone('Europe/Dublin')

# Task state constants
TASK_STATES = {
    'RUNNING': 'RUNNING',
    'PAUSED': 'PAUSED',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

# Configure socket timeout for FTP operations
socket.setdefaulttimeout(30)

class FTPConnectionManager:
    """Enhanced FTP connection manager with retry logic and better error handling"""
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        self.retry_count = 0
        last_error = None
        while self.retry_count < self.config['max_retries']:
            try:
                self.ftp = FTP()
                self.ftp.encoding = 'utf-8'
                self.ftp.connect(
                    self.config['host'],
                    self.config['port'],
                    self.config['timeout']
                )
                self.ftp.login(
                    user=self.config['user'],
                    passwd=self.config['passwd']
                )
                try:
                    self.ftp.cwd(self.config['remote_dir'])
                    return self.ftp
                except Exception as e:
                    raise ConnectionError(f"Directory change failed: {str(e)}")
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {self.retry_count + 1} failed: {str(e)}")
                self.retry_count += 1
                time.sleep(self.config['retry_delay'])
        raise ConnectionError(f"All retries failed. Last error: {str(last_error)}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if hasattr(self, 'ftp'):
                self.ftp.quit()
        except Exception as e:
            logger.warning(f"Error closing FTP connection: {str(e)}")

def get_ftp_config(schedule_id=None):
    """Get FTP configuration with schedule-specific overrides"""
    base_config = {
        'host': os.getenv('FTP_HOST', 'waws-prod-db3-169.ftp.azurewebsites.windows.net'),
        'user': os.getenv('FTP_USER', 'tzcftp\\tzcftp2'),
        'passwd': os.getenv('FTP_PASS', 'M6@yPcCldNWXsmoyW'),
        'port': int(os.getenv('FTP_PORT', 21)),
        'remote_dir': os.getenv('REMOTE_DIR', '/site/wwwroot/ArchiveFiles/Roadstone Galway'),
        'timeout': 60,
        'max_retries': 5,
        'retry_delay': 10
    }
    
    if schedule_id:
        try:
            schedule = ParsingSchedule.objects.get(pk=schedule_id)
            base_config['remote_dir'] = schedule.ftp_path
        except ParsingSchedule.DoesNotExist:
            logger.error(f"Schedule {schedule_id} not found")
    
    return base_config

def safe_decimal(value):
    """Convert value to Decimal safely with comprehensive cleaning"""
    if value is None:
        return None
    try:
        cleaned = ''.join(c for c in str(value).strip() 
                         if c.isdigit() or c in '.-').replace(',', '')
        return Decimal(cleaned) if cleaned else None
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.debug(f"Decimal conversion failed: {str(e)}")
        return None

def validate_xml_structure(xml_content):
    """Flexible XML validation that handles multiple root tag formats"""
    try:
        xml_content.seek(0)
        tree = ET.parse(xml_content)
        root = tree.getroot()
        
        if root is None:
            raise ValueError("Empty XML document")
        if root.tag not in ['BatchLogs', 'DailyXMLReport']:
            raise ValueError(f"Expected root tag 'BatchLogs' or 'DailyXMLReport', found '{root.tag}'")
            
        return tree, root
    except ET.ParseError as e:
        raise ValueError(f"XML parsing error: {str(e)}")
    except Exception as e:
        raise ValueError(f"XML validation failed: {str(e)}")

def parse_date_from_filename(filename):
    """Extract date from filenames with pattern validation"""
    try:
        if not filename.endswith('.xml'):
            logger.error(f"Invalid file extension: {filename}")
            return None

        # Verify filename pattern
        if '_' not in filename:
            logger.error(f"Missing date separator '_' in filename: {filename}")
            return None
            
        date_part = filename.rsplit('_', 1)[-1].split('.')[0]
        if len(date_part) < 6:  # Minimum: DDMMYY
            logger.error(f"Invalid date format in filename: {filename}")
            return None
            
        parsed_date = parser.parse(date_part, dayfirst=True).date()
        logger.debug(f"Successfully parsed date from filename: {parsed_date}")
        return parsed_date
        
    except Exception as e:
        logger.error(f"Filename date parse failed ({filename}): {str(e)}")
        return None

def int_or_none(value):
    """Safely convert value to integer or return None"""
    try:
        return int(value) if value and value.strip() else None
    except:
        return None

def process_oee_data(root, filename, date):
    """Process OEE Performance Data"""
    try:
        oee_perf = root.find('OEEPerformance')
        if not oee_perf:
            return 0

        obj, created = OEEDailyData.objects.update_or_create(
            date=date,
            defaults={
                'TotalProduction': safe_decimal(oee_perf.findtext('TotalProduction')),
                'TotalEmptyOut': safe_decimal(oee_perf.findtext('TotalEmptyOut')),
                'ProductionBatches': int_or_none(oee_perf.findtext('ProductionBatches')),
                'EmptyOutBatches': int_or_none(oee_perf.findtext('EmptyOutBatches'))
            }
        )
        return 1 if created else 0
    except Exception as e:
        logger.error(f"OEE Data error: {str(e)}")
        return 0

def process_plant_runtime(root, filename, date):
    """Process Plant Runtime Data from <PlantRunTime>"""
    try:
        runtime_data = {}
        runtime_mapping = {
            'Mixing Active': 'MixingActive',
            'Mixer': 'Mixer',
            'Screen': 'Screen',
            'Hot Elevator': 'HotElevator',
            'Dryer': 'Dryer',
            'Burner Flame On': 'BurnerFlameOn',
            'Slinger Forward': 'SlingerForward',
            'Slinger Reverse': 'SlingerReverse',
            'Collect Conveyor': 'CollectConveyor',
            'Dust Blower': 'DustBlower',
            'Dust Blower Rotary Valve': 'DustBlowerRotaryValve'
        }

        for rt in root.findall('.//PlantRunTime/RunTime'):
            item_name = rt.findtext('ItemName', '').strip()
            running_time = rt.findtext('RunningTime', '00:00:00')
            
            if item_name in runtime_mapping:
                field_name = runtime_mapping[item_name]
                runtime_data[field_name] = parse_duration(running_time)

        obj, created = PlantRunTime.objects.update_or_create(
            date=date,
            defaults=runtime_data
        )
        return 1 if created else 0
    except Exception as e:
        logger.error(f"Runtime error: {str(e)}")
        return 0

def process_daily_recipes(root, filename, date):
    """Process Recipe Totals from <RecipeTotals>"""
    try:
        count = 0
        for recipe in root.findall('.//RecipeTotals/RecipeTotal'):
            defaults = {
                'RecipeName': recipe.findtext('RecipeName'),
                'Total': safe_decimal(recipe.findtext('Total'))
            }
            obj, created = DailyRecipes.objects.update_or_create(
                date=date,
                RecipeNo=int_or_none(recipe.findtext('RecipeNo')),
                defaults=defaults
            )
            count += 1 if created else 0
        return count
    except Exception as e:
        logger.error(f"Recipe error: {str(e)}")
        return 0

def process_daily_materials(root, filename, date):
    """Process Material Totals from <MaterialTotals>"""
    try:
        count = 0
        # Process all material types
        for material in root.findall('.//MaterialTotals/*'):
            defaults = {
                'MaterialName': material.findtext('Name'),
                'Quantity': safe_decimal(material.findtext('Quantity'))
            }
            
            material_no = material.findtext('MaterialNo')
            if not material_no:
                continue

            obj, created = DailyMaterials.objects.update_or_create(
                date=date,
                MaterialNo=int_or_none(material_no),
                defaults=defaults
            )
            count += 1 if created else 0
        return count
    except Exception as e:
        logger.error(f"Material error: {str(e)}")
        return 0

def parse_duration(time_str):
    """Convert time string HH:MM:SS to seconds"""
    try:
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except:
        return 0

def process_batch(batch, filename):
    """Process individual batch with comprehensive field extraction and validation"""
    try:
        with transaction.atomic():
            batch_data = {
                'BatchNo': batch.findtext("BatchNo", "").strip(),
                'Time': batch.findtext("Time") or batch.findtext("Timestamp", "").strip(),
                'JobNo': batch.findtext("JobNo", "").strip(),
                'RecipeNo': batch.findtext("RecipeNo", "").strip(),
                'RecipeName': batch.findtext("RecipeName", "").strip(),
                'Bitumen_Actual': safe_decimal(batch.findtext("Bitumen/Actual", "")),
                'Filler_Actual': safe_decimal(batch.findtext("Filler/Actual", "")),
                'Reclaim_Actual': safe_decimal(batch.findtext("Reclaim/Actual", "")),
                'Temperature_Actual': safe_decimal(batch.findtext("Temperature/Actual", "")),
                'Bitumen_Target': safe_decimal(batch.findtext("Bitumen/Target", "")),
                'Filler_Target': safe_decimal(batch.findtext("Filler/Target", "")),
                'Reclaim_Target': safe_decimal(batch.findtext("Reclaim/Target", "")),
                'Temperature_Target': safe_decimal(batch.findtext("Temperature/Target", "")),
            }
            
            # Process HotBin data (limit to 8 bins)
            hot_bins = batch.findall("HotBin")
            for i, hot_bin in enumerate(hot_bins[:8], start=1):
                batch_data[f'HotBin{i}_Actual'] = safe_decimal(hot_bin.findtext("Actual", ""))
                batch_data[f'HotBin{i}_Target'] = safe_decimal(hot_bin.findtext("Target", ""))
            
            # Validate required fields
            if not all([batch_data['BatchNo'], batch_data['Time'], batch_data['JobNo']]):
                raise ValueError("Missing required batch fields")
            
            # Check for duplicates
            if BatchLog.objects.filter(
                BatchNo=batch_data['BatchNo'],
                Time=batch_data['Time'],
                JobNo=batch_data['JobNo']
            ).exists():
                logger.warning(f"Duplicate batch detected: {batch_data['BatchNo']}")
                return False
            
            # Create batch record
            BatchLog.objects.create(**batch_data)
            return True
        
    except Exception as e:
        logger.error(f"Error processing batch in {filename}: {str(e)}", exc_info=True)
        return False

def send_progress_update(task_id, data):
    """Send real-time progress updates via WebSocket"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'parsing_{task_id}',
            {
                "type": "progress.update",
                "data": data
            }
        )
    except Exception as e:
        logger.error(f"Failed to send WebSocket update: {str(e)}")

def acquire_task_lock():
    """Acquire distributed task lock"""
    return cache.add('parsing_lock', 'locked', settings.CACHE_LOCK_TIMEOUT)

def release_task_lock():
    """Release distributed task lock"""
    cache.delete('parsing_lock')

@shared_task
def dublin_task():
    with timezone.override(dublin_tz):
        print(f"Task time: {timezone.localtime()}")

@shared_task(
    bind=True,
    max_retries=5,
    time_limit=3600,
    soft_time_limit=1800,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_xml_files(self, schedule_id=None, resume_state=None):
    """
    Main XML processing task with:
    - Chunked file processing
    - Pause/resume functionality
    - Detailed progress tracking
    - Robust error handling
    """
    def _handle_pause(state_key, state_data):
        """Pause handling with timeout and conflict detection"""
        logger.info("Parsing paused")
        start_time = time.time()
        
        while cache.get('pause_parsing'):
            current_task_id = cache.get('current_parsing_task')
            if current_task_id != self.request.id:
                logger.info("New task started, aborting paused task")
                raise Ignore()
            
            if time.time() - start_time > 3600:  # 1 hour timeout
                logger.warning("Pause timeout reached")
                _save_state(state_key, state_data)
                raise SoftTimeLimitExceeded("Pause duration exceeded")
            
            time.sleep(5)
            self.update_state(state=TASK_STATES['PAUSED'], meta=state_data)

    def _process_single_file(ftp, ftp_config, filename, schedule_id, state_key):
        """Process individual XML file with comprehensive error handling"""
        file_batches = 0
        file_content = BytesIO()
        processed = False  # Track if any data was processed
        
        try:
            # Download file
            logger.info(f"⏳ Downloading {filename}")
            ftp.retrbinary(f"RETR {filename}", file_content.write)
            file_content.seek(0)
            logger.info(f"📥 Downloaded {filename} ({len(file_content.getvalue())} bytes)")

            # Parse XML with flexible validation
            tree, root = validate_xml_structure(file_content)
            batch_logs = root.findall(".//BatchLog")
            logger.info(f"🔍 Found {len(batch_logs)} batches in {filename}")
            
            # Process batches if any exist
            if batch_logs:
                batch_total = len(batch_logs)
                for batch_idx, batch in enumerate(batch_logs, 1):
                    if process_batch(batch, filename):
                        file_batches += 1
                        processed = True  # Mark as processed if any batches

                    # Update progress periodically
                    if batch_idx % max(1, batch_total//10) == 0 or batch_idx == batch_total:
                        progress_data = {
                            'current_file': filename,
                            'batches_processed': file_batches,
                            'state_key': state_key,
                            'batch_progress': f"{batch_idx}/{batch_total}",
                            'message': f'Processing batch {batch_idx} of {batch_total}'
                        }
                        self.update_state(state=TASK_STATES['RUNNING'], meta=progress_data)
                        send_progress_update(self.request.id, progress_data)

            # Extract date from filename (required for additional processing)
            date = parse_date_from_filename(filename)
            if not date:
                raise ValueError(f"Failed to parse date from filename: {filename}")

            # Process additional data models regardless of batches
            try:
                oee_count = process_oee_data(root, filename, date)
                runtime_count = process_plant_runtime(root, filename, date)
                recipes_count = process_daily_recipes(root, filename, date)
                materials_count = process_daily_materials(root, filename, date)
                
                if any([oee_count, runtime_count, recipes_count, materials_count]):
                    processed = True
                    logger.info(
                        f"Processed additional data - OEE: {oee_count}, Runtime: {runtime_count}, "
                        f"Recipes: {recipes_count}, Materials: {materials_count}"
                    )
            except Exception as e:
                logger.error(f"Additional data processing error: {str(e)}")

            # Determine final status
            if processed:
                status = 'success'
                error_msg = None
            else:
                status = 'skipped' 
                error_msg = 'No processable data found in file'

            # Record processing result
            ProcessedFile.objects.create(
                file_name=filename,
                file_type='XML',
                file_path=f"ftp://{ftp_config['host']}{ftp_config['remote_dir']}/{filename}",
                status=status,
                error_message=error_msg,
                trigger_source='scheduled' if schedule_id else 'manual',
                schedule_id=schedule_id
            )

            logger.info(f"✅ Successfully processed {filename} (Status: {status})")
            return file_batches

        except Exception as e:
            logger.error(f"❌ Error processing {filename}: {str(e)}")
            ProcessedFile.objects.create(
                file_name=filename,
                file_type='XML',
                file_path=f"ftp://{ftp_config['host']}{ftp_config['remote_dir']}/{filename}",
                status='error',
                error_message=str(e)[:500],
                trigger_source='scheduled' if schedule_id else 'manual',
                schedule_id=schedule_id
            )
            return 0
        finally:
            file_content.close()

    def _save_state(state_key, state):
        """Persist progress state for potential resume"""
        cache.set(state_key, state, timeout=86400)  # 24h expiration

    # Main task execution
    ftp_config = get_ftp_config(schedule_id)
    processed_files = resume_state['processed_count'] if resume_state else 0
    batches_processed = 0
    state_key = f'parsing_state_{self.request.id}'

    try:
        if not acquire_task_lock():
            raise Exception("Another parsing task is already running")

        # Initial state update
        initial_state = {
            'progress': 0,
            'description': "Initializing connection",
            'current_file': '',
            'processed_files': processed_files,
            'total_files': 0,
            'batches_processed': batches_processed,
            'state_key': state_key
        }
        self.update_state(state=TASK_STATES['RUNNING'], meta=initial_state)
        send_progress_update(self.request.id, initial_state)

        with FTPConnectionManager(ftp_config) as ftp:
            # File discovery logic
            if not resume_state:
                files = ftp.nlst()
                logger.info(f"Found files: {files}")
                xml_files = [f for f in files if f.lower().endswith('.xml')]
                
                if not xml_files:
                    logger.info("No XML files found")
                    return {
                        'status': 'completed',
                        'files_processed': 0,
                        'batches_processed': 0,
                        'progress': 100,
                        'message': 'No XML files found'
                    }
                
                processed_filenames = set(ProcessedFile.objects.filter(
                    file_name__in=xml_files
                ).values_list('file_name', flat=True))
                
                files_to_process = [f for f in xml_files if f not in processed_filenames]
            else:
                files_to_process = resume_state['remaining_files']

            total_files = len(files_to_process)
            chunk_size = getattr(settings, 'PROCESSING_CHUNK_SIZE', 25)

            # Process files in chunks
            for chunk_idx in range(0, len(files_to_process), chunk_size):
                chunk = files_to_process[chunk_idx:chunk_idx + chunk_size]
                
                for file_idx, filename in enumerate(chunk, 1):
                    try:
                        overall_progress = int((chunk_idx + file_idx) / total_files * 100)
                        progress_data = {
                            'progress': overall_progress,
                            'description': f"Processing {filename}",
                            'current_file': filename,
                            'processed_files': processed_files,
                            'total_files': total_files,
                            'batches_processed': batches_processed,
                            'state_key': state_key
                        }
                        self.update_state(state=TASK_STATES['RUNNING'], meta=progress_data)
                        send_progress_update(self.request.id, progress_data)

                        if cache.get('pause_parsing'):
                            _handle_pause(state_key, progress_data)

                        file_batches = _process_single_file(ftp, ftp_config, filename, schedule_id, state_key)
                        processed_files += 1
                        batches_processed += file_batches

                        # Save state for potential resume
                        cache.set(state_key, {
                            'last_processed': filename,
                            'processed_count': processed_files,
                            'remaining_files': files_to_process[chunk_idx + file_idx:],
                            'batches_processed': batches_processed
                        }, timeout=86400)

                        gc.collect()

                    except SoftTimeLimitExceeded:
                        logger.warning(f"Time limit approaching for {filename}")
                        cache.set(state_key, {
                            'last_processed': filename,
                            'processed_count': processed_files,
                            'remaining_files': files_to_process[chunk_idx + file_idx:],
                            'batches_processed': batches_processed
                        }, timeout=86400)
                        raise

                    except Exception as e:
                        logger.error(f"Failed to process {filename}: {str(e)}")
                        continue

        # Final completion
        completion_data = {
            'status': 'completed',
            'files_processed': processed_files,
            'batches_processed': batches_processed,
            'progress': 100,
            'message': 'Processing completed successfully'
        }
        send_progress_update(self.request.id, completion_data)
        return completion_data

    except SoftTimeLimitExceeded:
        logger.warning("Task approaching hard time limit")
        raise self.retry(countdown=300)
    
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        failure_data = {
            'status': 'failed',
            'progress': 100,
            'message': f'Task failed: {str(e)}'
        }
        send_progress_update(self.request.id, failure_data)
        raise self.retry(exc=e)
    
    finally:
        release_task_lock()
        cache.delete(f'parsing_state_{self.request.id}')

@shared_task
def monitor_stalled_tasks():
    """Cleanup and restart stuck tasks"""
    stalled = ProcessedFile.objects.filter(
        status='processing',
        export_time__lt=timezone.now()-timedelta(hours=1)
    )
    
    for file in stalled:
        logger.warning(f"Restarting stalled task: {file.task.id}")
        file.status = 'error'
        file.error_message = 'Timeout auto-restart'
        file.save()
        
        state = cache.get(f'parsing_state_{file.task.id}')
        if state:
            process_xml_files.delay(
                resume_state=state,
                schedule_id=file.schedule_id if file.schedule else None
            )

@shared_task(bind=True)
def check_interrupted_tasks(self):
    """Check for tasks that need recovery"""
    timeout_threshold = timezone.now() - timedelta(minutes=30)
    
    interrupted = ProcessedFile.objects.filter(
        status='processing',
        last_updated__lt=timeout_threshold
    ).select_related('task')
    
    for file in interrupted:
        logger.warning(f"Found interrupted task for file: {file.file_name}")
        file.status = 'interrupted'
        file.save()
        
        cache.set(
            f'task_recovery_{file.task.id}',
            {
                'last_file': file.file_name,
                'processed_files': ProcessedFile.objects.filter(
                    task=file.task, 
                    status='success'
                ).count(),
                'total_files': file.task.total_files
            },
            timeout=86400
        )

@shared_task
def scheduled_parse(schedule_id):
    """Entry point for scheduled parsing tasks"""
    try:
        schedule = ParsingSchedule.objects.get(pk=schedule_id, is_active=True)
        logger.info(f"Starting scheduled parse: {schedule.name}")
        task = process_xml_files.delay(schedule_id=schedule_id)
        cache.set('current_parsing_task', task.id)
        return task.id
    except ParsingSchedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found or inactive")
        return None
    except Exception as e:
        logger.error(f"Error starting scheduled parse: {str(e)}")
        raise

@shared_task
def start_parsing_task():
    """Start manual parsing process"""
    cache.set('pause_parsing', False)
    task = process_xml_files.delay()
    cache.set('current_parsing_task', task.id)
    return task.id

@shared_task
def pause_parsing():
    """Pause the parsing process"""
    cache.set('pause_parsing', True)
    return True

@shared_task
def resume_parsing():
    """Resume paused parsing process"""
    cache.set('pause_parsing', False)
    return True

@shared_task(bind=True)
def resume_parsing_task(self, original_task_id):
    """Resume an interrupted parsing task"""
    logger.info(f"Resuming task {original_task_id}")
    recovery_data = cache.get(f'task_recovery_{original_task_id}')
    logger.debug(f"Recovery data: {recovery_data}")
    
    if not recovery_data:
        raise ValueError("No recovery data found for task")
    
    original_task = ProcessedFile.objects.filter(task_id=original_task_id).first()
    schedule_id = original_task.schedule.id if original_task and original_task.schedule else None
    
    process_xml_files.delay(
        resume_state={
            'remaining_files': recovery_data.get('remaining_files', []),
            'processed_count': recovery_data.get('processed_files', 0),
            'last_processed': recovery_data.get('last_file', '')
        },
        schedule_id=schedule_id
    )

@shared_task
def cleanup_old_tasks(days=7):
    """Cleanup old task results and processed files"""
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_files, _ = ProcessedFile.objects.filter(
            export_time__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_files} old processed files")
        return {
            'status': 'completed',
            'files_deleted': deleted_files,
            'message': f'Cleaned up data older than {days} days'
        }
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise

def _send_ws_update(self, progress, message, error=False):
    """Helper method to send WebSocket updates"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "energy_updates",
            {
                "type": "task.update",
                "data": {
                    "progress": progress,
                    "message": message,
                    "error": error,
                    "task_id": self.request.id
                }
            }
        )
    except Exception as e:
        logger.error(f"WebSocket update failed: {str(e)}")

@shared_task(bind=True)
def fetch_energy_data(self):
    """
    Fetch energy data with:
    - Dublin timezone handling
    - Exact API URL date formatting (YYYY-MM-DD)
    - Duplicate prevention
    - Chunked processing
    - WebSocket progress updates
    """
    try:
        # 1. Get current time in Dublin
        dublin_now = timezone.now().astimezone(dublin_tz)
        
        # 2. Start from July 1, 2023 (Dublin time)
        start_date = dublin_tz.localize(datetime(2023, 7, 3))
        
        # 3. Find last fetched record (in Dublin time)
        last_record = EnergyData.objects.order_by('-timestamp').first()
        if last_record:
            start_date = last_record.timestamp + timedelta(seconds=1)
    
        # 4. Check if we're already up-to-date
        if start_date > dublin_now:
            _send_ws_update(self, 100, "Data is already current")
            return {
                'status': 'up_to_date',
                'message': 'Data is already current',
                'records_processed': 0
            }

        # 5. Format dates for API (naive YYYY-MM-DD in Dublin time)
        def format_api_date(dt):
            return dt.astimezone(dublin_tz).strftime('%Y-%m-%d')
        
        # 6. Process in daily chunks
        current_date = start_date
        records_added = 0
        total_days = (dublin_now - start_date).days + 1
        
        while current_date <= dublin_now:
            chunk_end = min(
                current_date + timedelta(days=1),  # Daily chunks
                dublin_now
            )
            
            # Format exactly like reference: "2025-04-01/2025-04-02"
            api_url = (
                f"https://tzcapi.azurewebsites.net/publicapi/GetConsumptions/"
                f"72/1716/{format_api_date(current_date)}/"
                f"{format_api_date(chunk_end)}"
            )
            
            # 7. Fetch and process data
            response = requests.get(
                api_url,
                headers={'x-api-key': settings.PRIORITY_METRICS_API_KEY},
                timeout=30
            )
            response.raise_for_status()
            
            new_records = []
            for record in response.json():
                # Parse record timestamp as Dublin time
                try:
                    record_time = dublin_tz.localize(
                        datetime.strptime(record["timestamp"], '%Y-%m-%dT%H:%M:%S')
                    )
                    
                    if not EnergyData.objects.filter(
                        timestamp=record_time,
                        meter_name=record["meterName"]
                    ).exists():
                        new_records.append(EnergyData(
                            date=record["timestamp"].split('T')[0],
                            timestamp=record_time,
                            meter_name=record["meterName"],
                            value=record["value"],
                            consumption=record["consumption"]
                        ))
                except Exception as e:
                    logger.error(f"Error processing record: {str(e)}")
                    continue
            
            if new_records:
                EnergyData.objects.bulk_create(new_records)
                records_added += len(new_records)
            
            # 8. Calculate progress
            days_processed = (chunk_end - start_date).days + 1
            progress = min(100, int((days_processed / total_days * 100)))
            
            # 9. Send WebSocket update
            async_to_sync(get_channel_layer().group_send)(
                f"energy_{self.request.id}",
                {
                    "type": "task.update",
                    "data": {
                        "progress": progress,
                        "message": f"Processed {format_api_date(current_date)}",
                        "records_added": records_added
                    }
                }
            )

            current_date = chunk_end + timedelta(seconds=1)

        # Final success update
        async_to_sync(get_channel_layer().group_send)(
            f"energy_{self.request.id}",
            {
                "type": "task.update",
                "data": {
                    "progress": 100,
                    "message": "Fetch completed successfully",
                    "records_added": records_added
                }
            }
        )
        
        return {
            'status': 'success',
            'records_added': records_added,
            'start_date': format_api_date(start_date),
            'end_date': format_api_date(dublin_now)
        }

    except Exception as e:
        logger.error(f"Fetch failed: {str(e)}", exc_info=True)
        
        # Send error update
        async_to_sync(get_channel_layer().group_send)(
            f"energy_{self.request.id}",
            {
                "type": "task.update",
                "data": {
                    "progress": 0,
                    "message": f"Error: {str(e)}",
                    "error": True
                }
            }
        )
        
        self.retry(exc=e, countdown=120)