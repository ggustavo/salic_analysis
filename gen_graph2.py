import pandas as pd
import os
import networkx as nx
import plotly.graph_objects as go

# Main directory where CSV files are stored
merged_files = "merged_files"

# Path to the CSV file
file_path = os.path.join(merged_files, "projetos_incentivadores.csv")

try:
    graph = nx.Graph()
    
    # Reading the CSV file with UTF-8 encoding
    df = pd.read_csv(file_path, encoding='utf-8')
    print(f"CSV file loaded successfully with {len(df)} rows.")
    
    # Mantendo as colunas com os nomes em português
    columns_to_keep = ['PRONAC', 'nome', 'cgccpf', 'total_doado', 'tipo_pessoa', 'UF', 'municipio']
    df_filtered = df[columns_to_keep]
    
    print(f"Filtered dataframe created with columns: {columns_to_keep}")

    # Creating nodes and edges
    for idx, row in df_filtered.iterrows():
        # Create project node with ID as string
        project_node = str(int(row['PRONAC']))
        if project_node not in graph:
            graph.add_node(project_node, label=project_node, color='gray')

        # Create incentivador node with ID as string
        incentivador_name = str(row['nome']).upper().strip() 
        incentivador_cgccpf = str(row['cgccpf']).upper().strip()
        
        incentivador_node = incentivador_cgccpf
        
        node_color = 'orange' if str(row['tipo_pessoa']).lower() == 'juridica' else 'lightblue'
        
        if incentivador_node not in graph:
            graph.add_node(incentivador_node, label=incentivador_name, color=node_color)
        
        # Create edge between incentivador and project
        graph.add_edge(incentivador_node, project_node)
        
        if idx % 1000 == 0:
            print(f"Processed {idx} rows.")
        if idx > 1000:
            break
        
    print(f"Graph created with {len(graph.nodes)} nodes and {len(graph.edges)} edges.")

    # Generate Plotly graph
    pos = nx.spring_layout(graph)  # Positions for all nodes
    edges = list(graph.edges())
    edge_trace = go.Scatter(
        x=[],
        y=[],
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')
    for edge in edges:
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace['x'] += (x0, x1, None)
        edge_trace['y'] += (y0, y1, None)

    node_trace = go.Scatter(
        x=[],
        y=[],
        text=[],
        mode='markers+text',
        textposition='top center',
        hoverinfo='text',
        marker=dict(size=10, color=[], line=dict(width=2)))
    
    for node in graph.nodes():
        x, y = pos[node]
        node_trace['x'] += (x,)
        node_trace['y'] += (y,)
        node_trace['text'] += (graph.nodes[node].get('label', ''),) #(node,)  # Tooltip with node ID
        node_trace['marker']['color'] += (graph.nodes[node].get('color', 'gray'),)

    fig = go.Figure(data=[edge_trace, node_trace],
                     layout=go.Layout(
                         showlegend=False,
                         hovermode='closest',
                         margin=dict(b=0, l=0, r=0, t=0),
                         xaxis=dict(showgrid=False, zeroline=False),
                         yaxis=dict(showgrid=False, zeroline=False)))
    
    # Save the Plotly graph to an HTML file
    fig.write_html("results/incentivadores.html", auto_open=True)
    print("Graph saved and displayed successfully.")

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




# 1-) Apresentar os dados 
# 2-) Problema com relacionamentos (resolvido)
# 3-) Análise das áreas culturais
# 4-) Análise dos segmentos culturais (no artigo são os 'subfields')
# 5-) Rede de proponentes
# 6-) Rede incentivadores

# https://versalic.cultura.gov.br/#/projetos/090347
# https://versalic.cultura.gov.br/#/projetos/128562
# https://versalic.cultura.gov.br/#/projetos/159594
# https://versalic.cultura.gov.br/#/projetos/210173