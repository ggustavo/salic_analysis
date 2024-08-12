import pandas as pd
import os

# Main directory where CSV files are stored
merged_files = "merged_files"
results_dir = "results"
file_path = os.path.join(merged_files, "projetos.csv")

# Ensure the results directory exists
os.makedirs(results_dir, exist_ok=True)

def generate_report(df, attribute, output_file):
    """Generate a report based on a given attribute and save it to a file."""
    try:
        with open(output_file, "w", encoding='utf-8') as file:
            # Total number of tuples
            total_tuples = len(df)
            file.write(f"Total number of tuples: {total_tuples}\n\n")
            
            # Group by the specified attribute and count
            counts = df.groupby(attribute).size()
            file.write(f"Project counts by {attribute}:\n")
            for value, count in counts.items():
                file.write(f"{value}: {count}\n")
            
            # Group by 'UF' (state) and count for each attribute
            grouped_by_uf = df.groupby('UF')
            
            for uf, group in grouped_by_uf:
                file.write(f"\nNome do Estado: {uf}\n")
                counts_by_uf = group.groupby(attribute).size()
                for value, count in counts_by_uf.items():
                    file.write(f"{value}: {count}\n")
                
        print(f"Report for '{attribute}' saved to {output_file}.")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{file_path}' não foi encontrado.")
    except pd.errors.EmptyDataError:
        print("Erro: O arquivo está vazio.")
    except pd.errors.ParserError:
        print("Erro: Houve um problema ao analisar o arquivo CSV.")
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
        import traceback
        print("Stack trace:")
        traceback.print_exc()

try:
    # Reading the CSV file with UTF-8 encoding
    df = pd.read_csv(file_path, encoding='utf-8')
    
    # Generate reports for 'area' and 'segmento'
    generate_report(df, 'area', os.path.join(results_dir, "project_report_area.txt"))
    generate_report(df, 'segmento', os.path.join(results_dir, "project_report_segmento.txt"))

except Exception as e:
    print(f"Erro inesperado: {str(e)}")
    import traceback
    print("Stack trace:")
    traceback.print_exc()