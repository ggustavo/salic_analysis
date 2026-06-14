import os
import sys
from dotenv import load_dotenv

# Ensure project root is in path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Load env variables from project root
dotenv_path = os.path.join(project_dir, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.task.trigger_rule import TriggerRule
from datetime import datetime, timedelta

# Import the core pipeline functions
from salic_pipeline import (
    verify_environment,
    check_api_connectivity,
    verify_disk_space,
    download_cultural_segments,
    validate_cultural_segments,
    initialize_checkpoints,
    preflight_projects_check,
    preflight_proposals_check,
    preflight_suppliers_check,
    preflight_incentivizers_check,
    preflight_proponents_check,
    download_projects,
    download_proposals,
    download_suppliers,
    download_incentivizers,
    download_proponents,
    validate_projects_data,
    validate_proposals_data,
    validate_suppliers_data,
    validate_incentivizers_data,
    validate_proponents_data,
    generate_ingestion_manifest,
    pipeline_success,
    generate_error_report
)

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

# Define the DAG with manual schedule
dag = DAG(
    'salic_pipeline',
    default_args=default_args,
    description='Resumable and Storage-Agnostic SALIC Ingestion Pipeline (18 Steps)',
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=['salic', 'pipeline', 'manual', 'minio'],
)


# Airflow-specific wrappers to handle XComs and run context
def airflow_generate_ingestion_manifest(**context):
    ti = context['ti']
    proj_stats = ti.xcom_pull(task_ids='validate_projects_data') or {'files_validated': 0, 'records_found': 0}
    prop_stats = ti.xcom_pull(task_ids='validate_proposals_data') or {'files_validated': 0, 'records_found': 0}
    supp_stats = ti.xcom_pull(task_ids='validate_suppliers_data') or {'files_validated': 0, 'records_found': 0}
    inc_stats = ti.xcom_pull(task_ids='validate_incentivizers_data') or {'files_validated': 0, 'records_found': 0}
    proponents_stats = ti.xcom_pull(task_ids='validate_proponents_data') or {'files_validated': 0, 'records_found': 0}
    return generate_ingestion_manifest(proj_stats, prop_stats, supp_stats, inc_stats, proponents_stats)


def airflow_generate_error_report(**context):
    dag_run = context['dag_run']
    
    # Locate failed task instances
    failed_tasks = []
    for instance in dag_run.get_task_instances():
        if instance.state == 'failed':
            failed_tasks.append({
                'task_id': instance.task_id,
                'state': instance.state,
                'execution_date': instance.execution_date.isoformat() if instance.execution_date else None
            })
    return generate_error_report(failed_tasks)


# ============= AIRFLOW OPERATORS DEFINITION =============

# Pre-checks
verify_env = PythonOperator(
    task_id='verify_environment',
    python_callable=verify_environment,
    dag=dag,
)

check_api = PythonOperator(
    task_id='check_api_connectivity',
    python_callable=check_api_connectivity,
    dag=dag,
)

verify_disk = PythonOperator(
    task_id='verify_disk_space',
    python_callable=verify_disk_space,
    dag=dag,
)

# Metadata
fetch_segments = PythonOperator(
    task_id='download_cultural_segments',
    python_callable=download_cultural_segments,
    dag=dag,
)

validate_segments = PythonOperator(
    task_id='validate_cultural_segments',
    python_callable=validate_cultural_segments,
    dag=dag,
)

init_checkpoints = PythonOperator(
    task_id='initialize_checkpoints',
    python_callable=initialize_checkpoints,
    dag=dag,
)

# Estimations
preflight_projects = PythonOperator(
    task_id='preflight_projects_check',
    python_callable=preflight_projects_check,
    dag=dag,
)

preflight_proposals = PythonOperator(
    task_id='preflight_proposals_check',
    python_callable=preflight_proposals_check,
    dag=dag,
)

preflight_suppliers = PythonOperator(
    task_id='preflight_suppliers_check',
    python_callable=preflight_suppliers_check,
    dag=dag,
)

preflight_incentivizers = PythonOperator(
    task_id='preflight_incentivizers_check',
    python_callable=preflight_incentivizers_check,
    dag=dag,
)

preflight_proponents = PythonOperator(
    task_id='preflight_proponents_check',
    python_callable=preflight_proponents_check,
    dag=dag,
)

# Core Ingestion
download_projects = PythonOperator(
    task_id='download_projects',
    python_callable=download_projects,
    dag=dag,
)

download_proposals = PythonOperator(
    task_id='download_proposals',
    python_callable=download_proposals,
    dag=dag,
)

download_suppliers = PythonOperator(
    task_id='download_suppliers',
    python_callable=download_suppliers,
    dag=dag,
)

download_incentivizers = PythonOperator(
    task_id='download_incentivizers',
    python_callable=download_incentivizers,
    dag=dag,
)

download_proponents = PythonOperator(
    task_id='download_proponents',
    python_callable=download_proponents,
    dag=dag,
)

# Post Ingestion Validations
validate_projects = PythonOperator(
    task_id='validate_projects_data',
    python_callable=validate_projects_data,
    dag=dag,
)

validate_proposals = PythonOperator(
    task_id='validate_proposals_data',
    python_callable=validate_proposals_data,
    dag=dag,
)

validate_suppliers = PythonOperator(
    task_id='validate_suppliers_data',
    python_callable=validate_suppliers_data,
    dag=dag,
)

validate_incentivizers = PythonOperator(
    task_id='validate_incentivizers_data',
    python_callable=validate_incentivizers_data,
    dag=dag,
)

validate_proponents = PythonOperator(
    task_id='validate_proponents_data',
    python_callable=validate_proponents_data,
    dag=dag,
)

# Manifest Consolidator
gen_manifest = PythonOperator(
    task_id='generate_ingestion_manifest',
    python_callable=airflow_generate_ingestion_manifest,
    dag=dag,
)

# Milestone Success / Failure
pipeline_ok = PythonOperator(
    task_id='pipeline_success_milestone',
    python_callable=pipeline_success,
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

pipeline_err = PythonOperator(
    task_id='pipeline_failure_milestone',
    python_callable=airflow_generate_error_report,
    trigger_rule=TriggerRule.ONE_FAILED,
    dag=dag,
)


# ============= GRAPH DEFINITION & DEPENDENCIES =============

# Sequential Setup & Metadata Ingestion
verify_env >> check_api >> verify_disk >> fetch_segments >> validate_segments >> init_checkpoints

# Parallel Pre-flight Queries after Checkpoint Init
init_checkpoints >> preflight_projects
init_checkpoints >> preflight_proposals
init_checkpoints >> preflight_suppliers
init_checkpoints >> preflight_incentivizers
init_checkpoints >> preflight_proponents

# Sequential flow for Projects: Preflight -> Download -> Validate
preflight_projects >> download_projects >> validate_projects

# Sequential flow for Proposals: Preflight -> Download -> Validate
preflight_proposals >> download_proposals >> validate_proposals

# Sequential flow for Suppliers: Preflight -> Download -> Validate
preflight_suppliers >> download_suppliers >> validate_suppliers

# Sequential flow for Incentivizers: Preflight -> Download -> Validate
preflight_incentivizers >> download_incentivizers >> validate_incentivizers

# Sequential flow for Proponents: Preflight -> Download -> Validate
preflight_proponents >> download_proponents >> validate_proponents

# Consolidate manifest once all validations are done
[validate_projects, validate_proposals, validate_suppliers, validate_incentivizers, validate_proponents] >> gen_manifest

# Mark pipeline success
gen_manifest >> pipeline_ok

# Trigger failure flow if any of the tasks upstream fail
all_upstream_tasks = [
    verify_env, check_api, verify_disk, fetch_segments, validate_segments, init_checkpoints,
    preflight_projects, preflight_proposals, preflight_suppliers, preflight_incentivizers, preflight_proponents,
    download_projects, download_proposals, download_suppliers, download_incentivizers, download_proponents,
    validate_projects, validate_proposals, validate_suppliers, validate_incentivizers, validate_proponents, gen_manifest
]
all_upstream_tasks >> pipeline_err
