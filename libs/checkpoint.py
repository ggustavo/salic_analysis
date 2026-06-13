import os
import logging
from libs.storage import StorageClient

logger = logging.getLogger("airflow.task")

class CheckpointManager:
    """Manages checkpoints for resumable downloads across local and S3 storage backends."""
    
    def __init__(self, raw_data_dir=None):
        # Retrieve the unified storage client instance
        self.storage = StorageClient.get_instance()
    
    def load_projects(self):
        new_key = ".checkpoints/projects.json"
        
        # Load from active storage (either local or S3)
        checkpoint = self.storage.load_json(new_key, default=None)
        if checkpoint:
            return checkpoint
        
        # Fallback to local legacy path: raw_data_dir/checkpoint.json
        local_legacy_path = os.path.join(self.storage.local_dir, "checkpoint.json")
        if os.path.exists(local_legacy_path):
            try:
                import json
                with open(local_legacy_path, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                # Save checkpoint into active storage (handles S3/local dynamically)
                self.save_projects(checkpoint)
                # Cleanup local legacy file
                os.remove(local_legacy_path)
                logger.info(f"Successfully migrated projects checkpoint from legacy file {local_legacy_path} to {new_key} in active storage.")
                return checkpoint
            except Exception as e:
                logger.warning(f"⚠️ Failed to migrate legacy projects checkpoint: {e}")
            
        return {"segment_index": 0, "offset": 0}
    
    def save_projects(self, checkpoint):
        self.storage.save_json(".checkpoints/projects.json", checkpoint)
        
    def load_proposals(self):
        new_key = ".checkpoints/proposals.json"
        
        checkpoint = self.storage.load_json(new_key, default=None)
        if checkpoint:
            return checkpoint
            
        # Fallback to local legacy path: raw_data_dir/checkpoint_proposals.json
        local_legacy_path = os.path.join(self.storage.local_dir, "checkpoint_proposals.json")
        if os.path.exists(local_legacy_path):
            try:
                import json
                with open(local_legacy_path, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                self.save_proposals(checkpoint)
                os.remove(local_legacy_path)
                logger.info(f"Successfully migrated proposals checkpoint from legacy file {local_legacy_path} to {new_key} in active storage.")
                return checkpoint
            except Exception as e:
                logger.warning(f"⚠️ Failed to migrate legacy proposals checkpoint: {e}")
            
        return {"offset": 0}
        
    def save_proposals(self, checkpoint):
        self.storage.save_json(".checkpoints/proposals.json", checkpoint)
        
    def load_suppliers(self):
        new_key = ".checkpoints/suppliers.json"
        
        checkpoint = self.storage.load_json(new_key, default=None)
        if checkpoint:
            return checkpoint
            
        return {"offset": 0}
        
    def save_suppliers(self, checkpoint):
        self.storage.save_json(".checkpoints/suppliers.json", checkpoint)
        
    def load_incentivizers(self):
        new_key = ".checkpoints/incentivizers.json"
        
        checkpoint = self.storage.load_json(new_key, default=None)
        if checkpoint:
            return checkpoint
            
        return {"offset": 0}
        
    def save_incentivizers(self, checkpoint):
        self.storage.save_json(".checkpoints/incentivizers.json", checkpoint)

    def load_proponents(self):
        new_key = ".checkpoints/proponents.json"
        
        checkpoint = self.storage.load_json(new_key, default=None)
        if checkpoint:
            return checkpoint
            
        return {"offset": 0}
        
    def save_proponents(self, checkpoint):
        self.storage.save_json(".checkpoints/proponents.json", checkpoint)

