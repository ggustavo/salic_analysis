import sys
import os
import logging
import shutil
import time
from datetime import datetime, UTC
from dotenv import load_dotenv

# Ensure the project root is in sys.path so 'libs' imports work correctly
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Load environment variables from .env in the project root
dotenv_path = os.path.join(project_dir, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Ensure modular package imports from libs folder
from libs.api import SalicAPI, CulturalSegments, Projects, Proposals, Suppliers, Incentivizers, Proponents
from libs.downloaders import ProjectsDownloader, ProposalsDownloader, SuppliersDownloader, IncentivizersDownloader, ProponentsDownloader
from libs.checkpoint import CheckpointManager
from libs.storage import StorageClient

logger = logging.getLogger("airflow.task")

# Configuration defaults
BATCH_SIZE = int(os.environ.get("SALIC_BATCH_SIZE", "100"))

MAX_OFFSET = os.environ.get("SALIC_MAX_OFFSET")
if MAX_OFFSET is not None:
    try:
        MAX_OFFSET = int(MAX_OFFSET)
    except ValueError:
        MAX_OFFSET = None

MAX_RETRIES = int(os.environ.get("SALIC_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.environ.get("SALIC_RETRY_DELAY", "5"))


# ============= 1. ENVIRONMENT & PRE-CHECKS =============

def verify_environment():
    """Step 1: Verify target storage client initialization and write permissions."""
    logger.info("--- STEP 1: VERIFYING ENVIRONMENT ---")
    try:
        storage = StorageClient.get_instance()
        logger.info(f"Active storage type: {storage.storage_type.upper()}")
        
        if storage.storage_type == "s3":
            logger.info(f"Target MinIO Endpoint: {storage.s3_endpoint}")
            logger.info(f"Target Bucket Name:   {storage.s3_bucket}")
        else:
            logger.info(f"Target Local Folder:   {storage.local_dir}")
        
        logger.info(f"BATCH_SIZE: {BATCH_SIZE}")
        logger.info(f"MAX_OFFSET: {MAX_OFFSET if MAX_OFFSET is not None else 'No limit'}")
        logger.info(f"MAX_RETRIES: {MAX_RETRIES}")
        logger.info(f"RETRY_DELAY: {RETRY_DELAY} seconds")

            
        if storage.check_connectivity():
            logger.info("✅ Environment verified: Storage backend is online and writable!")
            return {'status': 'verified', 'storage_type': storage.storage_type}
        else:
            raise Exception("Storage connection check returned False.")
    except Exception as e:
        logger.error(f"❌ Environment verification failed: {e}")
        raise


def check_api_connectivity():
    """Step 2: Check connectivity to the SALIC API base URL and log latency."""
    logger.info("--- STEP 2: CHECKING API CONNECTIVITY ---")
    api = SalicAPI(max_retries=1, retry_delay=1)
    start_time = time.time()
    if api.check_connectivity():
        latency = time.time() - start_time
        logger.info(f"✅ Connection successful! Latency: {latency:.2f}s")
        return {'status': 'connected', 'latency_seconds': latency}
    else:
        logger.error("❌ SALIC API base endpoint is offline or unreachable.")
        raise Exception("SALIC API connectivity check failed.")


def verify_disk_space():
    """Step 3: Check local partition space and warn if space is low."""
    logger.info("--- STEP 3: VERIFYING LOCAL DISK SPACE ---")
    try:
        storage = StorageClient.get_instance()
        
        # Ensure the directory exists or fallback to parent / current directory
        dir_to_check = storage.local_dir
        if not os.path.exists(dir_to_check):
            try:
                os.makedirs(dir_to_check, exist_ok=True)
            except Exception:
                dir_to_check = os.path.dirname(dir_to_check) or '.'
                if not os.path.exists(dir_to_check):
                    dir_to_check = '.'
                    
        total, used, free = shutil.disk_usage(dir_to_check)
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)
        pct_used = (used / total) * 100
        
        logger.info(f"Local Partition Stats ({storage.local_dir}):")
        logger.info(f"  Total Space: {total_gb:.2f} GB")
        logger.info(f"  Used Space:  {used_gb:.2f} GB ({pct_used:.1f}%)")
        logger.info(f"  Free Space:  {free_gb:.2f} GB")
        
        if storage.storage_type == "local" and free_gb < 0.5:
            raise Exception(f"Critical: Local space ({free_gb:.2f} GB) is below the 0.5 GB threshold for Local storage mode.")
        elif free_gb < 0.2:
            logger.warning(f"⚠️ Warning: Partition free space is extremely low ({free_gb:.2f} GB).")
            
        logger.info("✅ Disk space check successfully completed!")
        return {'free_gb': free_gb, 'used_percentage': pct_used}
    except Exception as e:
        logger.error(f"❌ Disk space verification failed: {e}")
        raise


# ============= 2. METADATA & CHECKPOINT OPERATIONS =============

def download_cultural_segments():
    """Step 4: Download master list of cultural segments from the API."""
    logger.info("--- STEP 4: DOWNLOADING CULTURAL SEGMENTS ---")
    fetcher = CulturalSegments(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    segments_data = fetcher.fetch_all()
    if not segments_data:
        raise Exception("Failed to download cultural segments list.")
    
    storage = StorageClient.get_instance()
    segments_key = "cultural_segments.json"
    storage.save_json(segments_key, segments_data)
    logger.info(f"✅ Saved cultural segments JSON to storage: {segments_key}")
    return {'status': 'success'}


def validate_cultural_segments():
    """Step 5: Verify the segments file structure and log segment breakdown."""
    logger.info("--- STEP 5: VALIDATING CULTURAL SEGMENTS ---")
    storage = StorageClient.get_instance()
    segments_key = "cultural_segments.json"
    
    data = storage.load_json(segments_key, default=None)
    if not data:
        raise Exception(f"Segments file '{segments_key}' does not exist or is empty in active storage.")
    
    segments = data.get('_embedded', {}).get('segmentos', [])
    if not segments:
        raise Exception("Segment list is empty or structure is invalid.")
    
    logger.info(f"✅ Validated cultural segments successfully! Found {len(segments)} segments:")
    for idx, seg in enumerate(segments, 1):
        logger.info(f"  Segment {idx:02d}: Code={seg.get('codigo')} | Name={seg.get('nome')}")
        
    return {'segments_count': len(segments)}


def initialize_checkpoints():
    """Step 6: Instantiate checkpoint manager, perform migrations, and log resume offsets."""
    logger.info("--- STEP 6: INITIALIZING AND LOGGING CHECKPOINTS ---")
    mgr = CheckpointManager()
    
    proj_ckpt = mgr.load_projects()
    prop_ckpt = mgr.load_proposals()
    supp_ckpt = mgr.load_suppliers()
    inc_ckpt = mgr.load_incentivizers()
    proponents_ckpt = mgr.load_proponents()
    
    logger.info("Current Resumable Checkpoint States:")
    logger.info(f"  Projects:  Segment Index = {proj_ckpt.get('segment_index')}, Offset = {proj_ckpt.get('offset')}")
    logger.info(f"  Proposals: Offset = {prop_ckpt.get('offset')}")
    logger.info(f"  Suppliers:  Offset = {supp_ckpt.get('offset')}")
    logger.info(f"  Incentivizers: Offset = {inc_ckpt.get('offset')}")
    logger.info(f"  Proponents: Offset = {proponents_ckpt.get('offset')}")
    
    return {
        'projects': proj_ckpt,
        'proposals': prop_ckpt,
        'suppliers': supp_ckpt,
        'incentivizers': inc_ckpt,
        'proponents': proponents_ckpt
    }


# ============= 3. INGESTION PRE-FLIGHT ESTIMATIONS =============

def preflight_projects_check():
    """Step 7: Check SALIC API total count of projects in the active resuming segment."""
    logger.info("--- STEP 7: PRE-FLIGHT PROJECTS CHECK ---")
    mgr = CheckpointManager()
    proj_ckpt = mgr.load_projects()
    seg_idx = proj_ckpt.get("segment_index", 0)
    
    storage = StorageClient.get_instance()
    segments_key = "cultural_segments.json"
    segments_data = storage.load_json(segments_key, default=None)
    if not segments_data:
        raise Exception(f"Segments file '{segments_key}' not found in active storage.")
    
    segments = segments_data.get('_embedded', {}).get('segmentos', [])
    if seg_idx >= len(segments):
        logger.info("🎉 Ingestion of projects for all segments was already completed in prior runs.")
        return {'status': 'all_segments_completed', 'remaining': 0}
        
    active_seg = segments[seg_idx]
    seg_code = active_seg['codigo']
    seg_name = active_seg['nome']
    
    proj_api = Projects(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    res = proj_api.fetch_page(seg_code, offset=0, limit=1)
    total_in_segment = res.get('total', 0) if res else 0
    
    resuming_offset = proj_ckpt.get('offset', 0)
    remaining = max(0, total_in_segment - resuming_offset)
    
    logger.info("Pre-flight Segment Breakdown:")
    logger.info(f"  Resuming from Segment [{seg_idx}/{len(segments)}]: {seg_name} (Code: {seg_code})")
    logger.info(f"  Total Projects in Segment: {total_in_segment}")
    logger.info(f"  Current Offset Position:   {resuming_offset}")
    logger.info(f"  Projects remaining:        {remaining}")
    
    return {'total_in_segment': total_in_segment, 'offset': resuming_offset, 'remaining': remaining}


def preflight_proposals_check():
    """Step 8: Query the proposals endpoint to determine system volume and remaining load."""
    logger.info("--- STEP 8: PRE-FLIGHT PROPOSALS CHECK ---")
    mgr = CheckpointManager()
    prop_ckpt = mgr.load_proposals()
    resuming_offset = prop_ckpt.get('offset', 0)
    
    prop_api = Proposals(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    res = prop_api.fetch_page(offset=0, limit=1)
    total_proposals = res.get('total', 0) if res else 0
    
    remaining = max(0, total_proposals - resuming_offset)
    logger.info(f"  Total Proposals in SALIC System: {total_proposals}")
    logger.info(f"  Resuming from Offset:            {resuming_offset}")
    logger.info(f"  Proposals remaining to ingest:   {remaining}")
    
    return {'total_proposals': total_proposals, 'offset': resuming_offset, 'remaining': remaining}


def preflight_suppliers_check():
    """Step 9: Query the suppliers endpoint to determine system volume and remaining load."""
    logger.info("--- STEP 9: PRE-FLIGHT SUPPLIERS CHECK ---")
    mgr = CheckpointManager()
    supp_ckpt = mgr.load_suppliers()
    resuming_offset = supp_ckpt.get('offset', 0)
    
    supp_api = Suppliers(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    res = supp_api.fetch_page(offset=0, limit=1)
    total_suppliers = res.get('total', 0) if res else 0
    
    remaining = max(0, total_suppliers - resuming_offset)
    logger.info(f"  Total Suppliers in SALIC System: {total_suppliers}")
    logger.info(f"  Resuming from Offset:           {resuming_offset}")
    logger.info(f"  Suppliers remaining to ingest:   {remaining}")
    
    return {'total_suppliers': total_suppliers, 'offset': resuming_offset, 'remaining': remaining}


def preflight_incentivizers_check():
    """Step 9b: Query the incentivizers endpoint to determine system volume and remaining load."""
    logger.info("--- STEP 9b: PRE-FLIGHT INCENTIVIZERS CHECK ---")
    mgr = CheckpointManager()
    inc_ckpt = mgr.load_incentivizers()
    resuming_offset = inc_ckpt.get('offset', 0)
    
    inc_api = Incentivizers(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    res = inc_api.fetch_page(offset=0, limit=1)
    total_incentivizers = res.get('total', 0) if res else 0
    
    remaining = max(0, total_incentivizers - resuming_offset)
    logger.info(f"  Total Incentivizers in SALIC System: {total_incentivizers}")
    logger.info(f"  Resuming from Offset:                {resuming_offset}")
    logger.info(f"  Incentivizers remaining to ingest:   {remaining}")
    
    return {'total_incentivizers': total_incentivizers, 'offset': resuming_offset, 'remaining': remaining}


def preflight_proponents_check():
    """Step 9c: Query the proponents endpoint to determine system volume and remaining load."""
    logger.info("--- STEP 9c: PRE-FLIGHT PROPONENTS CHECK ---")
    mgr = CheckpointManager()
    proponents_ckpt = mgr.load_proponents()
    resuming_offset = proponents_ckpt.get('offset', 0)
    
    proponents_api = Proponents(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    res = proponents_api.fetch_page(offset=0, limit=1)
    total_proponents = res.get('total', 0) if res else 0
    
    remaining = max(0, total_proponents - resuming_offset)
    logger.info(f"  Total Proponents in SALIC System: {total_proponents}")
    logger.info(f"  Resuming from Offset:             {resuming_offset}")
    logger.info(f"  Proponents remaining to ingest:   {remaining}")
    
    return {'total_proponents': total_proponents, 'offset': resuming_offset, 'remaining': remaining}


# ============= 4. INGESTION CORE DOWNLOADS =============

def download_projects():
    """Step 10: Download projects segment by segment from SALIC."""
    logger.info("--- STEP 10: DOWNLOADING PROJECTS ---")
    downloader = ProjectsDownloader(
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    success = downloader.download(batch_size=BATCH_SIZE, max_offset=MAX_OFFSET)
    if not success:
        raise Exception("Failed downloading projects.")
    logger.info("✅ Projects download batch completed successfully.")
    return {'status': 'success'}


def download_proposals():
    """Step 11: Download proposals sequentially from SALIC."""
    logger.info("--- STEP 11: DOWNLOADING PROPOSALS ---")
    downloader = ProposalsDownloader(
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    success = downloader.download(batch_size=BATCH_SIZE, max_offset=MAX_OFFSET)
    if not success:
        raise Exception("Failed downloading proposals.")
    logger.info("✅ Proposals download batch completed successfully.")
    return {'status': 'success'}


def download_suppliers():
    """Step 12: Download suppliers sequentially from SALIC."""
    logger.info("--- STEP 12: DOWNLOADING SUPPLIERS ---")
    downloader = SuppliersDownloader(
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    success = downloader.download(batch_size=BATCH_SIZE, max_offset=MAX_OFFSET)
    if not success:
        raise Exception("Failed downloading suppliers.")
    logger.info("✅ Suppliers download batch completed successfully.")
    return {'status': 'success'}


def download_incentivizers():
    """Step 12b: Download incentivizers sequentially from SALIC."""
    logger.info("--- STEP 12b: DOWNLOADING INCENTIVIZERS ---")
    downloader = IncentivizersDownloader(
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    success = downloader.download(batch_size=BATCH_SIZE, max_offset=MAX_OFFSET)
    if not success:
        raise Exception("Failed downloading incentivizers.")
    logger.info("✅ Incentivizers download batch completed successfully.")
    return {'status': 'success'}


def download_proponents():
    """Step 12c: Download proponents sequentially from SALIC."""
    logger.info("--- STEP 12c: DOWNLOADING PROPONENTS ---")
    downloader = ProponentsDownloader(
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    success = downloader.download(batch_size=BATCH_SIZE, max_offset=MAX_OFFSET)
    if not success:
        raise Exception("Failed downloading proponents.")
    logger.info("✅ Proponents download batch completed successfully.")
    return {'status': 'success'}


# ============= 5. DATA VALIDATION (JSON INTEGRITY CHECK) =============

def validate_projects_data():
    """Step 13: Validate JSON structure integrity and count records for projects."""
    logger.info("--- STEP 13: VALIDATING DOWNLOADED PROJECTS ---")
    storage = StorageClient.get_instance()
    files = storage.list_files("projects")
    
    file_count = 0
    record_count = 0
    corrupted_count = 0
    
    for file_key in files:
        if file_key.endswith(".json"):
            file_count += 1
            try:
                content = storage.load_json(file_key, default=None)
                if content is not None:
                    if isinstance(content, list):
                        record_count += len(content)
                    else:
                        record_count += 1
                else:
                    corrupted_count += 1
                    logger.error(f"❌ Corrupted or empty JSON file in active storage: {file_key}")
            except Exception as e:
                corrupted_count += 1
                logger.error(f"❌ Exception parsing JSON {file_key}: {e}")
                    
    logger.info("Projects Data Validation Report:")
    logger.info(f"  Files Validated: {file_count}")
    logger.info(f"  Records Found:   {record_count}")
    logger.info(f"  Corrupted Files: {corrupted_count}")
    
    if corrupted_count > 0:
        raise Exception(f"Validation failed: {corrupted_count} corrupted project JSON files detected.")
    
    return {'files_validated': file_count, 'records_found': record_count}


def validate_proposals_data():
    """Step 14: Validate JSON structure integrity and count records for proposals."""
    logger.info("--- STEP 14: VALIDATING DOWNLOADED PROPOSALS ---")
    storage = StorageClient.get_instance()
    files = storage.list_files("proposals")
    
    file_count = 0
    record_count = 0
    corrupted_count = 0
    
    for file_key in files:
        if file_key.endswith(".json"):
            file_count += 1
            try:
                content = storage.load_json(file_key, default=None)
                if content is not None:
                    if isinstance(content, list):
                        record_count += len(content)
                    else:
                        record_count += 1
                else:
                    corrupted_count += 1
                    logger.error(f"❌ Corrupted or empty JSON file in active storage: {file_key}")
            except Exception as e:
                corrupted_count += 1
                logger.error(f"❌ Exception parsing JSON {file_key}: {e}")
                
    logger.info("Proposals Data Validation Report:")
    logger.info(f"  Files Validated: {file_count}")
    logger.info(f"  Records Found:   {record_count}")
    logger.info(f"  Corrupted Files: {corrupted_count}")
    
    if corrupted_count > 0:
        raise Exception(f"Validation failed: {corrupted_count} corrupted proposal JSON files detected.")
        
    return {'files_validated': file_count, 'records_found': record_count}


def validate_suppliers_data():
    """Step 15: Validate JSON structure integrity and count records for suppliers."""
    logger.info("--- STEP 15: VALIDATING DOWNLOADED SUPPLIERS ---")
    storage = StorageClient.get_instance()
    files = storage.list_files("suppliers")
    
    file_count = 0
    record_count = 0
    corrupted_count = 0
    
    for file_key in files:
        if file_key.endswith(".json"):
            file_key_str = file_key
            file_count += 1
            try:
                content = storage.load_json(file_key_str, default=None)
                if content is not None:
                    if isinstance(content, list):
                        record_count += len(content)
                    else:
                        record_count += 1
                else:
                    corrupted_count += 1
                    logger.error(f"❌ Corrupted or empty JSON file in active storage: {file_key_str}")
            except Exception as e:
                corrupted_count += 1
                logger.error(f"❌ Exception parsing JSON {file_key_str}: {e}")
                
    logger.info("Suppliers Data Validation Report:")
    logger.info(f"  Files Validated: {file_count}")
    logger.info(f"  Records Found:   {record_count}")
    logger.info(f"  Corrupted Files: {corrupted_count}")
    
    if corrupted_count > 0:
        raise Exception(f"Validation failed: {corrupted_count} corrupted supplier JSON files detected.")
        
    return {'files_validated': file_count, 'records_found': record_count}


def validate_incentivizers_data():
    """Step 15b: Validate JSON structure integrity and count records for incentivizers."""
    logger.info("--- STEP 15b: VALIDATING DOWNLOADED INCENTIVIZERS ---")
    storage = StorageClient.get_instance()
    files = storage.list_files("incentivizers")
    
    file_count = 0
    record_count = 0
    corrupted_count = 0
    
    for file_key in files:
        if file_key.endswith(".json"):
            file_key_str = file_key
            file_count += 1
            try:
                content = storage.load_json(file_key_str, default=None)
                if content is not None:
                    if isinstance(content, list):
                        record_count += len(content)
                    else:
                        record_count += 1
                else:
                    corrupted_count += 1
                    logger.error(f"❌ Corrupted or empty JSON file in active storage: {file_key_str}")
            except Exception as e:
                corrupted_count += 1
                logger.error(f"❌ Exception parsing JSON {file_key_str}: {e}")
                
    logger.info("Incentivizers Data Validation Report:")
    logger.info(f"  Files Validated: {file_count}")
    logger.info(f"  Records Found:   {record_count}")
    logger.info(f"  Corrupted Files: {corrupted_count}")
    
    if corrupted_count > 0:
        raise Exception(f"Validation failed: {corrupted_count} corrupted incentivizer JSON files detected.")
        
    return {'files_validated': file_count, 'records_found': record_count}


def validate_proponents_data():
    """Step 15c: Validate JSON structure integrity and count records for proponents."""
    logger.info("--- STEP 15c: VALIDATING DOWNLOADED PROPONENTS ---")
    storage = StorageClient.get_instance()
    files = storage.list_files("proponents")
    
    file_count = 0
    record_count = 0
    corrupted_count = 0
    
    for file_key in files:
        if file_key.endswith(".json"):
            file_key_str = file_key
            file_count += 1
            try:
                content = storage.load_json(file_key_str, default=None)
                if content is not None:
                    if isinstance(content, list):
                        record_count += len(content)
                    else:
                        record_count += 1
                else:
                    corrupted_count += 1
                    logger.error(f"❌ Corrupted or empty JSON file in active storage: {file_key_str}")
            except Exception as e:
                corrupted_count += 1
                logger.error(f"❌ Exception parsing JSON {file_key_str}: {e}")
                
    logger.info("Proponents Data Validation Report:")
    logger.info(f"  Files Validated: {file_count}")
    logger.info(f"  Records Found:   {record_count}")
    logger.info(f"  Corrupted Files: {corrupted_count}")
    
    if corrupted_count > 0:
        raise Exception(f"Validation failed: {corrupted_count} corrupted proponent JSON files detected.")
        
    return {'files_validated': file_count, 'records_found': record_count}


# ============= 6. CONSOLIDATION & MANIFESTS =============

def generate_ingestion_manifest(proj_stats=None, prop_stats=None, supp_stats=None, inc_stats=None, proponents_stats=None):
    """Step 16: Scans keys, sizes, records and merges statistics into a run manifest JSON."""
    logger.info("--- STEP 16: GENERATING INGESTION MANIFEST ---")
    
    if proj_stats is None:
        proj_stats = {'files_validated': 0, 'records_found': 0}
    if prop_stats is None:
        prop_stats = {'files_validated': 0, 'records_found': 0}
    if supp_stats is None:
        supp_stats = {'files_validated': 0, 'records_found': 0}
    if inc_stats is None:
        inc_stats = {'files_validated': 0, 'records_found': 0}
    if proponents_stats is None:
        proponents_stats = {'files_validated': 0, 'records_found': 0}
        
    storage = StorageClient.get_instance()
    
    # Calculate folder sizes dynamically from active storage
    def get_path_size_bytes(prefix):
        size = 0
        for file_key in storage.list_files(prefix):
            size += storage.get_file_size(file_key)
        return size
        
    proj_bytes = get_path_size_bytes("projects")
    prop_bytes = get_path_size_bytes("proposals")
    supp_bytes = get_path_size_bytes("suppliers")
    inc_bytes = get_path_size_bytes("incentivizers")
    proponents_bytes = get_path_size_bytes("proponents")
    
    total_size_mb = (proj_bytes + prop_bytes + supp_bytes + inc_bytes + proponents_bytes) / (1024 * 1024)
    
    manifest = {
        'timestamp': datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'storage_type': storage.storage_type,
        'status': 'completed',
        'summary': {
            'total_files': proj_stats['files_validated'] + prop_stats['files_validated'] + supp_stats['files_validated'] + inc_stats['files_validated'] + proponents_stats['files_validated'],
            'total_records': proj_stats['records_found'] + prop_stats['records_found'] + supp_stats['records_found'] + inc_stats['records_found'] + proponents_stats['records_found'],
            'total_size_mb': round(total_size_mb, 2)
        },
        'components': {
            'projects': {
                'files': proj_stats['files_validated'],
                'records': proj_stats['records_found'],
                'size_bytes': proj_bytes
            },
            'proposals': {
                'files': prop_stats['files_validated'],
                'records': prop_stats['records_found'],
                'size_bytes': prop_bytes
            },
            'suppliers': {
                'files': supp_stats['files_validated'],
                'records': supp_stats['records_found'],
                'size_bytes': supp_bytes
            },
            'incentivizers': {
                'files': inc_stats['files_validated'],
                'records': inc_stats['records_found'],
                'size_bytes': inc_bytes
            },
            'proponents': {
                'files': proponents_stats['files_validated'],
                'records': proponents_stats['records_found'],
                'size_bytes': proponents_bytes
            }
        }
    }
    
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    manifest_key = f"manifests/manifest_{timestamp_str}.json"
    storage.save_json(manifest_key, manifest)
    
    logger.info("==================================================")
    logger.info("🎉 INGESTION RUN SUMMARY MANIFEST COMPILED! 🎉")
    logger.info(f"Storage Type:  {storage.storage_type.upper()}")
    logger.info(f"Manifest path: {manifest_key}")
    logger.info(f"  Total Ingested Records: {manifest['summary']['total_records']}")
    logger.info(f"  Total Ingested Batches: {manifest['summary']['total_files']}")
    logger.info(f"  Total Storage Size:     {manifest['summary']['total_size_mb']:.2f} MB")
    logger.info("==================================================")
    
    return manifest


# ============= 7. SUCCESS & ERROR REPORTING BRANCHES =============

def pipeline_success():
    """Step 17: Visual milestone showing the ingestion completed successfully."""
    logger.info("🎉 SUCCESS: Entire SALIC API pipeline finished with no errors! 🎉")
    return {'status': 'success'}


def generate_error_report(failed_tasks=None):
    """Step 18: Fallback task that compiles and writes detailed diagnostic reports upon failures."""
    logger.error("❌ FAILURE DETECTED: SALIC API download pipeline failed! ❌")
    
    if failed_tasks is None:
        failed_tasks = []
        
    # Capture checkpoint state from active storage
    mgr = CheckpointManager()
    proj_ckpt = mgr.load_projects()
    prop_ckpt = mgr.load_proposals()
    supp_ckpt = mgr.load_suppliers()
    inc_ckpt = mgr.load_incentivizers()
    proponents_ckpt = mgr.load_proponents()
    
    storage = StorageClient.get_instance()
    
    error_report = {
        'timestamp': datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'storage_type': storage.storage_type,
        'status': 'failed',
        'failed_tasks': failed_tasks,
        'checkpoints_state': {
            'projects': proj_ckpt,
            'proposals': prop_ckpt,
            'suppliers': supp_ckpt,
            'incentivizers': inc_ckpt,
            'proponents': proponents_ckpt
        },
        'troubleshooting_guidelines': [
            "1. Check network connectivity to the SALIC API base URL: https://api.salic.cultura.gov.br",
            "2. If S3 storage is enabled, verify MinIO service status and credentials.",
            "3. If Local storage is enabled, check disk write permissions and free space.",
            "4. Review individual task logs on the Airflow Webserver to trace timeouts or JSON formatting errors.",
            "5. Checkpoint offsets were preserved safely. Trigger the DAG manually again to resume seamlessly."
        ]
    }
    
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_key = f"errors/error_report_{timestamp_str}.json"
    storage.save_json(report_key, error_report)
    
    logger.error("==================================================")
    logger.error(f"❌ DIAGNOSTIC ERROR REPORT GENERATED: {report_key}")
    logger.error(f"  Storage Type: {storage.storage_type.upper()}")
    logger.error(f"  Failed Tasks: {[t.get('task_id') for t in failed_tasks]}")
    logger.error("  Resumable state has been captured. You can safely restart the manual run.")
    logger.error("==================================================")
    
    raise Exception(f"SALIC pipeline execution failed in task(s): {[t.get('task_id') for t in failed_tasks]}. Report key: {report_key}")


def main():
    logger.info("Starting standalone SALIC Pipeline execution...")
    try:
        # Step 1: Verify environment
        verify_environment()

        # Step 2: Check API connectivity
        check_api_connectivity()
        
        # Step 3: Verify disk space
        verify_disk_space()
        
        # Step 4: Download cultural segments
        download_cultural_segments()
        
        # Step 5: Validate cultural segments
        validate_cultural_segments()
        
        # Step 6: Initialize checkpoints
        initialize_checkpoints()
        
        # Step 7-9: Preflight checks
        preflight_projects_check()
        preflight_proposals_check()
        preflight_suppliers_check()
        preflight_incentivizers_check()
        preflight_proponents_check()
        
        # Step 10-12: Core downloads
        download_suppliers()
        download_incentivizers()
        download_proponents()
        download_projects()
        download_proposals()
        
        # Step 13-15: Validation after download
        proj_stats = validate_projects_data()
        prop_stats = validate_proposals_data()
        supp_stats = validate_suppliers_data()
        inc_stats = validate_incentivizers_data()
        proponents_stats = validate_proponents_data()
        
        # Step 16: Generate manifest
        generate_ingestion_manifest(proj_stats, prop_stats, supp_stats, inc_stats, proponents_stats)
        
        # Step 17: Pipeline success milestone
        pipeline_success()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        # Build a simulated failed tasks list for standalone mode
        failed_tasks_info = [{
            'task_id': 'standalone_execution',
            'state': 'failed',
            'error_message': str(e)
        }]
        try:
            generate_error_report(failed_tasks_info)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
