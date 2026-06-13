# Package initializer for SALIC Airflow package
import os
from dotenv import load_dotenv

# Load environmental variables from the .env file located inside this package directory
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)
