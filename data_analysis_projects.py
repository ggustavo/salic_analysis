import pandas as pd
import os

# Main directory where CSV files are stored
merged_files = "merged_files"
file_path = os.path.join(merged_files, "projetos.csv")

def generate_report():
    try:
        df = pd.read_csv(file_path, encoding='utf-8')       
        
        # Convertendo colunas para numérico, tratando possíveis erros
        df['valor_aprovado'] = pd.to_numeric(df['valor_aprovado'], errors='coerce')
        df['valor_captado'] = pd.to_numeric(df['valor_captado'], errors='coerce')
        
        filtro = df['valor_captado'] > df['valor_aprovado']
        projetos_filtrados = df[filtro]
        
        # Contando a quantidade de projetos
        quantidade_projetos = projetos_filtrados.shape[0]
        
        print(f"Quantidade de projetos onde valor_aprovado é maior que valor_captado: {quantidade_projetos}")
        
        # Print the first 5 projects, with each column of data for a project printed on a separate line
        for index, row in projetos_filtrados.head(1).iterrows():
            print(f"Projeto {index + 1}:")
            for col in projetos_filtrados.columns:
                pass
                #print(f"  {col}: {row[col]}")
                #print()  # Blank line for better readability between projects
        

        
    
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
        import traceback
        print("Stack trace:")
        traceback.print_exc()

# Executando a função
generate_report()
