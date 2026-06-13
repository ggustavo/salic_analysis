import os
import time
import logging
from libs.checkpoint import CheckpointManager
from libs.api import CulturalSegments, Projects, Proposals, Suppliers, Incentivizers, Proponents
from libs.utils import sanitize_name
from libs.storage import StorageClient

logger = logging.getLogger("airflow.task")

class ProjectsDownloader:
    def __init__(self, raw_data_dir="raw_data", max_retries=3, retry_delay=5):
        self.storage = StorageClient.get_instance()
        self.checkpoint_manager = CheckpointManager()
        self.segments_fetcher = CulturalSegments(max_retries=max_retries, retry_delay=retry_delay)
        self.projects_fetcher = Projects(max_retries=max_retries, retry_delay=retry_delay)
    
    def download(self, batch_size=100, max_offset=None):
        logger.info("Starting Projects Download")
        
        # Load segments from storage client
        segments_key = "cultural_segments.json"
        segments_data = self.storage.load_json(segments_key, default=None)
        if not segments_data:
            logger.info("📥 Fetching segments...")
            segments_data = self.segments_fetcher.fetch_all()
            if segments_data:
                self.storage.save_json(segments_key, segments_data)
        
        if not segments_data:
            logger.error("❌ Failed to fetch segments")
            return False
        
        segments = segments_data.get('_embedded', {}).get('segmentos', [])
        checkpoint = self.checkpoint_manager.load_projects()
        start_seg_idx = checkpoint.get("segment_index", 0)
        start_offset = checkpoint.get("offset", 0)
        
        logger.info(f"📍 Resuming projects from Segment {start_seg_idx}, Offset {start_offset}")
        
        for seg_idx in range(start_seg_idx, len(segments)):
            segment = segments[seg_idx]
            seg_code = segment['codigo']
            seg_name = segment['nome']
            seg_folder = sanitize_name(seg_name)
            
            logger.info(f"📌 Processing [{seg_idx}/{len(segments)}] Segment: {seg_name}")
            
            # Reset start_offset to 0 for subsequent segments
            seg_start_offset = start_offset if seg_idx == start_seg_idx else 0
            
            success = self._download_segment(seg_idx, seg_code, seg_folder, seg_start_offset, batch_size, max_offset)
            if not success:
                logger.warning(f"⚠️ Paused or failed segment {seg_name} download.")
                return False
                
        logger.info("✅ All projects downloaded successfully!")
        return True
    
    def _download_segment(self, seg_idx, seg_code, seg_folder, start_offset, batch_size, max_offset):
        current_offset = start_offset
        has_more = True
        iteration_count = 0
        
        while has_more:
            if max_offset is not None and iteration_count >= max_offset:
                logger.info(f"⏹️ Max offset ({max_offset}) reached for segment {seg_code}")
                # Save checkpoint at this state
                self.checkpoint_manager.save_projects({
                    "segment_index": seg_idx,
                    "offset": current_offset,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                })
                return True
            
            logger.info(f"Fetching projects batch at offset {current_offset} (limit {batch_size})...")
            data = self.projects_fetcher.fetch_page(seg_code, current_offset, batch_size)
            if not data:
                logger.error(f"❌ Failed to fetch projects for segment code {seg_code} at offset {current_offset}")
                # Save checkpoint at current state so we don't lose progress
                self.checkpoint_manager.save_projects({
                    "segment_index": seg_idx,
                    "offset": current_offset,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                })
                return False
            
            projects = data.get('_embedded', {}).get('projetos', [])
            if not projects:
                has_more = False
                logger.info(f"✅ No more projects for segment code {seg_code}")
                break
            
            # Save projects batch in S3 or Local Disk using unified storage key
            batch_key = f"projects/{seg_folder}/batch_{current_offset}.json"
            self.storage.save_json(batch_key, projects)
            logger.info(f"💾 Saved {len(projects)} projects to active storage as: {batch_key}")
            
            current_offset += batch_size
            iteration_count += 1
            
            # Update checkpoint
            self.checkpoint_manager.save_projects({
                "segment_index": seg_idx,
                "offset": current_offset,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            
            # Small rate-limiting delay
            time.sleep(0.1)
            
        # Move to next segment
        self.checkpoint_manager.save_projects({
            "segment_index": seg_idx + 1,
            "offset": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        })
        return True


class ProposalsDownloader:
    def __init__(self, raw_data_dir="raw_data", max_retries=3, retry_delay=5):
        self.storage = StorageClient.get_instance()
        self.checkpoint_manager = CheckpointManager()
        self.proposals_fetcher = Proposals(max_retries=max_retries, retry_delay=retry_delay)
    
    def download(self, batch_size=100, max_offset=None):
        logger.info("Starting Proposals Download")
        
        checkpoint = self.checkpoint_manager.load_proposals()
        current_offset = checkpoint.get("offset", 0)
        
        logger.info(f"📍 Resuming proposals from offset {current_offset}")
        
        has_more = True
        iteration_count = 0
        
        while has_more:
            if max_offset is not None and iteration_count >= max_offset:
                logger.info(f"⏹️ Max offset ({max_offset}) reached for proposals")
                break
            
            logger.info(f"Fetching proposals batch at offset {current_offset} (limit {batch_size})...")
            data = self.proposals_fetcher.fetch_page(current_offset, batch_size)
            if not data:
                logger.error(f"❌ Failed to fetch proposals at offset {current_offset}")
                return False
            
            proposals = data.get('_embedded', {}).get('propostas', [])
            if not proposals:
                has_more = False
                logger.info("✅ No more proposals to download")
                break
            
            # Save proposals batch in S3 or Local Disk using unified storage key
            batch_key = f"proposals/batch_{current_offset}.json"
            self.storage.save_json(batch_key, proposals)
            logger.info(f"💾 Saved {len(proposals)} proposals to active storage as: {batch_key}")
            
            current_offset += batch_size
            iteration_count += 1
            
            self.checkpoint_manager.save_proposals({
                "offset": current_offset,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            
            time.sleep(0.1)
            
        logger.info("✅ Proposals download completed!")
        return True


class SuppliersDownloader:
    def __init__(self, raw_data_dir="raw_data", max_retries=3, retry_delay=5):
        self.storage = StorageClient.get_instance()
        self.checkpoint_manager = CheckpointManager()
        self.suppliers_fetcher = Suppliers(max_retries=max_retries, retry_delay=retry_delay)
    
    def download(self, batch_size=100, max_offset=None):
        logger.info("Starting Suppliers Download")
        
        checkpoint = self.checkpoint_manager.load_suppliers()
        current_offset = checkpoint.get("offset", 0)
        
        logger.info(f"📍 Resuming suppliers from offset {current_offset}")
        
        has_more = True
        iteration_count = 0
        
        while has_more:
            if max_offset is not None and iteration_count >= max_offset:
                logger.info(f"⏹️ Max offset ({max_offset}) reached for suppliers")
                break
            
            logger.info(f"Fetching suppliers batch at offset {current_offset} (limit {batch_size})...")
            data = self.suppliers_fetcher.fetch_page(current_offset, batch_size)
            if not data:
                logger.error(f"❌ Failed to fetch suppliers at offset {current_offset}")
                return False
            
            suppliers = data.get('_embedded', {}).get('fornecedores', [])
            if not suppliers:
                has_more = False
                logger.info("✅ No more suppliers to download")
                break
            
            # Save suppliers batch in S3 or Local Disk using unified storage key
            batch_key = f"suppliers/batch_{current_offset}.json"
            self.storage.save_json(batch_key, suppliers)
            logger.info(f"💾 Saved {len(suppliers)} suppliers to active storage as: {batch_key}")
            
            current_offset += batch_size
            iteration_count += 1
            
            self.checkpoint_manager.save_suppliers({
                "offset": current_offset,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            
            time.sleep(0.1)
            
        logger.info("✅ Suppliers download completed!")
        return True


class IncentivizersDownloader:
    def __init__(self, raw_data_dir="raw_data", max_retries=3, retry_delay=5):
        self.storage = StorageClient.get_instance()
        self.checkpoint_manager = CheckpointManager()
        self.incentivizers_fetcher = Incentivizers(max_retries=max_retries, retry_delay=retry_delay)
    
    def download(self, batch_size=100, max_offset=None):
        logger.info("Starting Incentivizers Download")
        
        checkpoint = self.checkpoint_manager.load_incentivizers()
        current_offset = checkpoint.get("offset", 0)
        
        logger.info(f"📍 Resuming incentivizers from offset {current_offset}")
        
        has_more = True
        iteration_count = 0
        
        while has_more:
            if max_offset is not None and iteration_count >= max_offset:
                logger.info(f"⏹️ Max offset ({max_offset}) reached for incentivizers")
                break
            
            logger.info(f"Fetching incentivizers batch at offset {current_offset} (limit {batch_size})...")
            data = self.incentivizers_fetcher.fetch_page(current_offset, batch_size)
            if not data:
                logger.error(f"❌ Failed to fetch incentivizers at offset {current_offset}")
                return False
            
            incentivizers = data.get('_embedded', {}).get('incentivadores', [])
            if not incentivizers:
                has_more = False
                logger.info("✅ No more incentivizers to download")
                break
            
            # Save incentivizers batch in S3 or Local Disk using unified storage key
            batch_key = f"incentivizers/batch_{current_offset}.json"
            self.storage.save_json(batch_key, incentivizers)
            logger.info(f"💾 Saved {len(incentivizers)} incentivizers to active storage as: {batch_key}")
            
            current_offset += batch_size
            iteration_count += 1
            
            self.checkpoint_manager.save_incentivizers({
                "offset": current_offset,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            
            time.sleep(0.1)
            
        logger.info("✅ Incentivizers download completed!")
        return True


class ProponentsDownloader:
    def __init__(self, raw_data_dir="raw_data", max_retries=3, retry_delay=5):
        self.storage = StorageClient.get_instance()
        self.checkpoint_manager = CheckpointManager()
        self.proponents_fetcher = Proponents(max_retries=max_retries, retry_delay=retry_delay)
    
    def download(self, batch_size=100, max_offset=None):
        logger.info("Starting Proponents Download")
        
        checkpoint = self.checkpoint_manager.load_proponents()
        current_offset = checkpoint.get("offset", 0)
        
        logger.info(f"📍 Resuming proponents from offset {current_offset}")
        
        has_more = True
        iteration_count = 0
        
        while has_more:
            if max_offset is not None and iteration_count >= max_offset:
                logger.info(f"⏹️ Max offset ({max_offset}) reached for proponents")
                break
            
            logger.info(f"Fetching proponents batch at offset {current_offset} (limit {batch_size})...")
            data = self.proponents_fetcher.fetch_page(current_offset, batch_size)
            if not data:
                logger.error(f"❌ Failed to fetch proponents at offset {current_offset}")
                return False
            
            proponents = data.get('_embedded', {}).get('proponentes', [])
            if not proponents:
                has_more = False
                logger.info("✅ No more proponents to download")
                break
            
            # Save proponents batch in S3 or Local Disk using unified storage key
            batch_key = f"proponents/batch_{current_offset}.json"
            self.storage.save_json(batch_key, proponents)
            logger.info(f"💾 Saved {len(proponents)} proponents to active storage as: {batch_key}")
            
            current_offset += batch_size
            iteration_count += 1
            
            self.checkpoint_manager.save_proponents({
                "offset": current_offset,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            
            time.sleep(0.1)
            
        logger.info("✅ Proponents download completed!")
        return True

