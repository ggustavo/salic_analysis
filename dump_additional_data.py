import pandas as pd
import requests
import os
import json
import time

# Main directory where CSV files are stored and results will be saved
merged_files = "merged_files"
results_dir = merged_files
file_path = os.path.join(merged_files, "projetos.csv")
control_file = os.path.join(results_dir, "control2.json")
output_csv = os.path.join(results_dir, "projetos_incentivadores.csv")
error_file = os.path.join(results_dir, "errors.json")

def fetch_incentivador_data(pronac):
    """Fetch incentivador data from the API for a given PRONAC."""
    pronac_formatted = str(pronac).zfill(6)
    url = f"https://api.salic.cultura.gov.br/v1/incentivadores/?PRONAC={pronac_formatted}"
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check for HTTP errors
            data = response.json()
            return data.get('_embedded', {}).get('incentivadores', [])
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1}: Failed to fetch data for PRONAC={pronac_formatted}: {e}")
            if attempt < retries - 1:
                time.sleep(60)  # Wait before retrying
            else:
                # Log PRONAC with error
                log_error(pronac, str(e))
                return []

def log_error(pronac, error_message):
    """Log the PRONAC with error to an error file."""
    errors = {}
    if os.path.exists(error_file):
        with open(error_file, 'r') as f:
            errors = json.load(f)
    errors[pronac] = error_message
    with open(error_file, 'w') as f:
        json.dump(errors, f)

def process_projects():
    """Process projects with valor_captado > 0.0 and fetch incentivador data."""
    os.makedirs(results_dir, exist_ok=True)

    control_data = {'last_pronac': None}
    
    if os.path.exists(control_file):
        with open(control_file, 'r') as f:
            control_data = json.load(f)
    
    last_pronac = control_data.get('last_pronac', None)
    
    try:
        print(f"Processing projects from '{file_path}'...")
        df = pd.read_csv(file_path, encoding='utf-8')
        
        positive_value_projects = df[df['valor_captado'] > 0.0].sort_values(by='PRONAC')
        
        any_data_processed = False
        
        if last_pronac:
            print(f"Starting from PRONAC={last_pronac} as per the last successful record.")

        for _, row in positive_value_projects.iterrows():
            pronac = row['PRONAC']
            if last_pronac and pronac <= last_pronac:
                continue  # Skip projects up to the last successfully processed PRONAC
            try:
                incentivadores = fetch_incentivador_data(pronac)
                if incentivadores:
                    if len(incentivadores) == 0:
                        # Log PRONAC with zero incentivadores as an error
                        log_error(pronac, "No incentivadores found.")
                        print(f"No incentivadores found for PRONAC={pronac}. Added to error log.")
                        break  # Stop processing if no incentivadores are found
                    print(f"{len(incentivadores)} Incentivador(es) were found for PRONAC={pronac}.")
                    data = []
                    for inc in incentivadores:
                        data.append({
                            'PRONAC': pronac,
                            'nome': inc.get('nome', ''),
                            'cgccpf': inc.get('cgccpf', ''),
                            'total_doado': inc.get('total_doado', 0.0),
                            'tipo_pessoa': inc.get('tipo_pessoa', ''),
                            'UF': inc.get('UF', ''),
                            'municipio': inc.get('municipio', '')
                        })
                    if data:
                        result_df = pd.DataFrame(data)
                        if not os.path.exists(output_csv):
                            result_df.to_csv(output_csv, index=False, encoding='utf-8')
                        else:
                            result_df.to_csv(output_csv, mode='a', header=False, index=False, encoding='utf-8')
                        any_data_processed = True
                    control_data['last_pronac'] = pronac
                    with open(control_file, 'w') as f:
                        json.dump(control_data, f)
                else:
                    # Log PRONAC with no incentivadores as an error
                    log_error(pronac, "No data found for PRONAC.")
                    print(f"No data found for PRONAC={pronac}. Added to error log.")
                    break  # Stop processing if no data is found
            except requests.RequestException as e:
                print(f"Error processing PRONAC={pronac}: {e}")
                log_error(pronac, f"Connection error: {e}")
                time.sleep(60)  # Wait before retrying
            except Exception as e:
                print(f"Error processing PRONAC={pronac}: {e}")
                log_error(pronac, f"Unexpected error: {e}")

        if not any_data_processed:
            print("No new data was processed.")

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except pd.errors.EmptyDataError:
        print("Error: The file is empty.")
    except pd.errors.ParserError:
        print("Error: Problem parsing the CSV file.")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        print("Stack trace:")
        traceback.print_exc()

# Execute the process
process_projects()