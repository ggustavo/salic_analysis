import os
import json
import logging
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

logger = logging.getLogger("airflow.task")

class StorageClient:
    """Unified storage client for Local File System and S3/MinIO Object Storage."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Singleton instance getter."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.storage_type = os.environ.get("SALIC_STORAGE_TYPE", "local").lower()
        self.local_dir = os.path.abspath(os.environ.get("SALIC_RAW_DATA_DIR", "raw_data"))
        
        # MinIO/S3 credentials and settings
        self.s3_endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        self.s3_access_key = os.environ.get("MINIO_ROOT_USER", "arida")
        self.s3_secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "4r1d4*m1n10*")
        self.s3_bucket = os.environ.get("MINIO_BUCKET_NAME", "salic")
        
        # Standardize endpoint URI for boto3
        if not self.s3_endpoint.startswith("http://") and not self.s3_endpoint.startswith("https://"):
            self.s3_endpoint = f"http://{self.s3_endpoint}"
            
        self.s3_client = None
        
        if self.storage_type == "s3":
            logger.info(f"Initializing MinIO S3 client for bucket '{self.s3_bucket}' on {self.s3_endpoint}")
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
                config=Config(signature_version='s3v4'),
                region_name='us-east-1'  # Dummy region for MinIO
            )
        else:
            logger.info(f"Initializing Local storage client targeting folder: {self.local_dir}")
            os.makedirs(self.local_dir, exist_ok=True)

    def _normalize_key(self, key_path):
        """Standardize keys to use S3-friendly forward slashes and strip leading slashes."""
        key = key_path.replace("\\", "/")
        if key.startswith("/"):
            key = key[1:]
        return key

    def ensure_bucket_exists(self):
        """Automatically checks and creates the target S3 bucket if it's missing."""
        if self.storage_type == "s3" and self.s3_client:
            try:
                self.s3_client.head_bucket(Bucket=self.s3_bucket)
                logger.info(f"MinIO bucket '{self.s3_bucket}' already exists.")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                # 404 means bucket doesn't exist
                if error_code == '404' or e.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 404:
                    logger.info(f"Bucket '{self.s3_bucket}' not found. Creating it now...")
                    try:
                        self.s3_client.create_bucket(Bucket=self.s3_bucket)
                        logger.info(f"✅ MinIO bucket '{self.s3_bucket}' successfully created!")
                    except Exception as ex:
                        raise Exception(f"Failed to create bucket '{self.s3_bucket}': {ex}")
                else:
                    raise Exception(f"Failed connection check to MinIO bucket '{self.s3_bucket}': {e}")

    def check_connectivity(self):
        """Validates that the storage backend is online and writeable."""
        if self.storage_type == "s3":
            try:
                # Test connectivity by listing buckets or accessing our target bucket
                self.ensure_bucket_exists()
                return True
            except Exception as e:
                logger.error(f"❌ MinIO connectivity test failed: {e}")
                return False
        else:
            # Local writeability test
            try:
                os.makedirs(self.local_dir, exist_ok=True)
                test_path = os.path.join(self.local_dir, ".storage_write_test")
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("test")
                os.remove(test_path)
                return True
            except Exception as e:
                logger.error(f"❌ Local storage writeability check failed: {e}")
                return False

    def save_json(self, key_path, data):
        """Saves data as a structured JSON object to S3 or local disk."""
        normalized_key = self._normalize_key(key_path)
        
        if self.storage_type == "s3" and self.s3_client:
            try:
                json_str = json.dumps(data, indent=4, ensure_ascii=False)
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=normalized_key,
                    Body=json_str,
                    ContentType='application/json'
                )
                logger.debug(f"Saved to S3: s3://{self.s3_bucket}/{normalized_key}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to save s3://{self.s3_bucket}/{normalized_key}: {e}")
                raise
        else:
            full_path = os.path.join(self.local_dir, os.path.normpath(key_path))
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                logger.debug(f"Saved to Local Disk: {full_path}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to save locally to {full_path}: {e}")
                raise

    def load_json(self, key_path, default=None):
        """Loads data from a JSON object on S3 or local disk."""
        normalized_key = self._normalize_key(key_path)
        
        if self.storage_type == "s3" and self.s3_client:
            try:
                response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=normalized_key)
                content = response['Body'].read().decode('utf-8')
                return json.loads(content)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code in ['NoSuchKey', 'NoSuchBucket', '404']:
                    logger.debug(f"Key not found in S3 (returning default): s3://{self.s3_bucket}/{normalized_key}")
                    return default if default is not None else {}
                else:
                    logger.error(f"❌ S3 read error for s3://{self.s3_bucket}/{normalized_key}: {e}")
                    raise
            except Exception as e:
                logger.error(f"❌ Failed to read s3://{self.s3_bucket}/{normalized_key}: {e}")
                raise
        else:
            full_path = os.path.join(self.local_dir, os.path.normpath(key_path))
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"⚠️ Error reading local JSON from {full_path}: {e}. Returning default.")
            return default if default is not None else {}

    def list_files(self, prefix=""):
        """Recursively lists relative paths (keys) starting with the specified prefix."""
        normalized_prefix = self._normalize_key(prefix)
        if normalized_prefix and not normalized_prefix.endswith("/"):
            normalized_prefix += "/"
            
        file_keys = []
        
        if self.storage_type == "s3" and self.s3_client:
            try:
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=normalized_prefix)
                for page in pages:
                    for obj in page.get('Contents', []):
                        file_keys.append(obj['Key'])
                return file_keys
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == 'NoSuchBucket':
                    return []
                raise
        else:
            full_dir = os.path.join(self.local_dir, os.path.normpath(prefix))
            if not os.path.exists(full_dir):
                return []
                
            for root, _, files in os.walk(full_dir):
                for f in files:
                    full_file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_file_path, self.local_dir)
                    # Standardize separator to forward slashes for cross-platform compatibility
                    file_keys.append(rel_path.replace("\\", "/"))
            return file_keys

    def get_file_size(self, key_path):
        """Gets the size of the file in bytes."""
        normalized_key = self._normalize_key(key_path)
        
        if self.storage_type == "s3" and self.s3_client:
            try:
                response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=normalized_key)
                return response.get('ContentLength', 0)
            except Exception:
                return 0
        else:
            full_path = os.path.join(self.local_dir, os.path.normpath(key_path))
            if os.path.exists(full_path):
                try:
                    return os.path.getsize(full_path)
                except Exception:
                    pass
            return 0
