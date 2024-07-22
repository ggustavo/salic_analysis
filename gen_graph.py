import pandas as pd
import os


def read_and_display_csv(file_path):
    try:
       
        df = pd.read_csv(file_path)
        
        
        print(df.head(2))
        
    except FileNotFoundError:
        print(f"Erro: O arquivo '{file_path}' não foi encontrado.")
    except pd.errors.EmptyDataError:
        print("Erro: O arquivo está vazio.")
    except pd.errors.ParserError:
        print("Erro: Problema ao analisar o arquivo CSV.")
    except Exception as e:
        print(f"Erro inesperado: {e}")

# Main directory where CSV files are stored
merged_files = "merged_files"

# Caminho para o arquivo CSV
file_path = os.path.join(merged_files, "projetos.csv")

# Chama a função
read_and_display_csv(file_path)