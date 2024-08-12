import pandas as pd
import os
import networkx as nx
import plotly.graph_objects as go

# Main directory where CSV files are stored
merged_files = "merged_files"

# Path to the CSV file
file_path = os.path.join(merged_files, "projetos.csv")

try:
    graph = nx.Graph()
    
    # Reading the CSV file with UTF-8 encoding
    df = pd.read_csv(file_path, nrows=100, encoding='utf-8')  # Adjusted to 10,000 rows
    print(f"CSV file loaded successfully with {len(df)} rows.")
    
    # Mantendo as colunas com os nomes em português
    columns_to_keep = ['PRONAC', 'nome', 'area', 'cgccpf', 'ano_projeto', 'UF', 'municipio', 'proponente', 'situacao']
    df_filtered = df[columns_to_keep]
    
    print(f"Filtered dataframe created with columns: {columns_to_keep}")

    # Creating nodes and edges
    for idx, row in df_filtered.iterrows():
        # Create project node with ID as string
        project_node = str(row['nome'])
        #project_node = str(row['PRONAC'])
        graph.add_node(project_node, label=row['nome'], area=row['area'], color='blue')

        # Create proponent node if it doesn't exist, with ID as string
        proponent_node = str(row['proponente'])
        if proponent_node not in graph:
            graph.add_node(proponent_node, color='gray')

        # Create edge between project and proponent
        graph.add_edge(project_node, proponent_node)
        
        if idx % 1000 == 0:
            print(f"Processed {idx} rows.")

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
        node_trace['text'] += (node,)  # Tooltip with node ID
        node_trace['marker']['color'] += (graph.nodes[node].get('color', 'blue'),)

    fig = go.Figure(data=[edge_trace, node_trace],
                     layout=go.Layout(
                         showlegend=False,
                         hovermode='closest',
                         margin=dict(b=0, l=0, r=0, t=0),
                         xaxis=dict(showgrid=False, zeroline=False),
                         yaxis=dict(showgrid=False, zeroline=False)))
    
    # Save the Plotly graph to an HTML file
    fig.write_html("results/project_network.html", auto_open=True)
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
