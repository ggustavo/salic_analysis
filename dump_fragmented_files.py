import requests
import os
import json

def download_csv(base_url, tipo, main_directory):
    # Creates the main directory if it does not exist
    if not os.path.exists(main_directory):
        os.makedirs(main_directory)
    
    # Creates the specific directory for the data type if it does not exist
    directory = os.path.join(main_directory, tipo)
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    control_file = os.path.join(directory, f"{tipo}_control.json")
    if os.path.exists(control_file):
        with open(control_file, 'r') as f:
            control_data = json.load(f)
            last_offset = control_data.get('last_offset', 0)
    else:
        last_offset = 0

    limit = 100
    offset = last_offset
    while True:
        url = f"{base_url}&offset={offset}&limit={limit}&format=csv"
        response = requests.get(url)
        if response.status_code == 200:
            content = response.content
            if len(content) == 0:
                print(f"No more data to download for {tipo}")
                break
            file_path = os.path.join(directory, f"{tipo}_{offset}.csv")
            with open(file_path, 'wb') as file:
                file.write(content)
            print(f"Downloaded: {file_path}")
            offset += limit
            with open(control_file, 'w') as f:
                json.dump({'last_offset': offset}, f)
        else:
            print(f"Failed to download: {url} with status code {response.status_code}")
            break

# Main directory to store the data
main_directory = "fragmented_files"

# Calls the download_csv function for each data type
download_csv("https://api.salic.cultura.gov.br/v1/projetos?sort=PRONAC:asc", "projetos", main_directory)
download_csv("https://api.salic.cultura.gov.br/v1/incentivadores?sort=total_doado:desc", "incentivadores", main_directory)
download_csv("https://api.salic.cultura.gov.br/v1/fornecedores?", "fornecedores", main_directory)
download_csv("https://api.salic.cultura.gov.br/v1/proponentes?", "proponentes", main_directory)
download_csv("https://api.salic.cultura.gov.br/v1/propostas?", "propostas", main_directory)



