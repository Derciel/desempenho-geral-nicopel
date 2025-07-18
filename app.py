# index.py (CORRIGIDO E ADAPTATIVO)
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import io, base64

# Importa a instância do app e os layouts das páginas
from index import app, server
from pages import clientes, franquias

# --- LAYOUT PRINCIPAL E COMPONENTES ---
app.layout = html.Div([
    dcc.Store(id='store-dados-originais'),
    dcc.Store(id='store-dados-clientes'),
    dcc.Store(id='store-dados-franquias'),
    
    dbc.Row(dbc.Col(
        html.Div([
            html.Img(src=('https://i.ibb.co/zWJstk81/logo-nicopel-8.png'), height="50px"),
            html.H1("Painel de Análise de Desempenho", className="text-white ms-3")
        ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
        style={'backgroundColor': "#007BFF", 'padding': '15px', 'borderRadius': '5px', 'textAlign': 'center', 'marginBottom': '20px'}
    )),
    
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content', className="p-4")
])

upload_component = html.Div([
    html.H3("Selecione o arquivo para análise", className="text-center mb-4"),
    dcc.Upload(
        id='upload-data',
        children=html.Div(['Arraste e solte ou ', html.A('selecione seu arquivo')]),
        style={'width': '100%', 'height': '120px', 'lineHeight': '120px', 'borderWidth': '2px', 'borderStyle': 'dashed',
               'borderRadius': '10px', 'textAlign': 'center', 'margin': '20px 0'}
    ),
    html.Div(id='output-upload-status')
])

# --- FUNÇÃO DE PROCESSAMENTO GERAL E ADAPTATIVA ---
def processar_arquivo_geral(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded)) if 'xls' in filename else pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        df_original = df.copy()
        df.columns = [str(col).strip() for col in df.columns]

        df['Data Emissao'] = pd.to_datetime(df.get('Data Emissao'), dayfirst=True, errors='coerce')
        df['R$ Total'] = pd.to_numeric(df.get('R$ Total'), errors='coerce')

        df_clientes, df_franquias = None, None

        # Tenta processar a análise de Clientes (sem depender de franquia)
        colunas_clientes = ['Data Emissao', 'R$ Total', 'Nome Fantasia', 'Vendedor']
        if all(col in df.columns for col in colunas_clientes):
            df_cl = df.dropna(subset=colunas_clientes).copy()
            if not df_cl.empty:
                faturamento_total = df_cl.groupby('Nome Fantasia')['R$ Total'].sum().reset_index().rename(columns={'R$ Total': 'Faturamento Total'})
                ultimas_compras = df_cl.sort_values('Data Emissao').drop_duplicates('Nome Fantasia', keep='last')[['Nome Fantasia', 'Data Emissao', 'Vendedor']].rename(columns={'Data Emissao': 'Ultima Compra', 'Vendedor': 'Vendedor da Ultima Compra'})
                df_clientes = pd.merge(faturamento_total, ultimas_compras, on='Nome Fantasia')
                df_clientes['Dias Sem Comprar'] = (df_cl['Data Emissao'].max() - df_clientes['Ultima Compra']).dt.days

        # Tenta processar a análise de Franquias (apenas se a coluna existir)
        colunas_franquias = ['Data Emissao', 'R$ Total', 'FRANQUIA', 'Descrição Item', 'Categoria']
        if all(col in df.columns for col in colunas_franquias):
            df_franquias = df.dropna(subset=colunas_franquias).copy()

        if df_clientes is None and df_franquias is None:
             return None, None, None, "Erro: O arquivo não contém as colunas mínimas necessárias (ex: 'Data Emissao', 'R$ Total', 'Nome Fantasia')."

        return df_original, df_clientes, df_franquias, f"Arquivo '{filename}' carregado com sucesso."
    except Exception as e:
        return None, None, None, f'Ocorreu um erro ao processar o arquivo: {e}'


# --- CALLBACKS ---

# Callback 1: Processa o arquivo e redireciona para a tela de seleção
@app.callback(
    [Output('output-upload-status', 'children'),
     Output('store-dados-originais', 'data'),
     Output('store-dados-clientes', 'data'),
     Output('store-dados-franquias', 'data'),
     Output('url', 'pathname')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def processa_e_redireciona(contents, filename):
    if contents:
        df_original, df_clientes, df_franquias, message = processar_arquivo_geral(contents, filename)
        
        json_original = df_original.to_json(date_format='iso', orient='split') if df_original is not None else None
        json_clientes = df_clientes.to_json(date_format='iso', orient='split') if df_clientes is not None else None
        json_franquias = df_franquias.to_json(date_format='iso', orient='split') if df_franquias is not None else None

        if json_clientes or json_franquias:
            return dbc.Alert(message, color="success"), json_original, json_clientes, json_franquias, '/selecao'
        
        return dbc.Alert(message, color="danger"), None, None, None, '/'
    
    return "", None, None, None, '/'

# Callback 2: "Roteador" - Decide qual página mostrar com base na URL
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname'),
    [State('store-dados-clientes', 'data'),
     State('store-dados-franquias', 'data')]
)
def display_page(pathname, data_clientes, data_franquias):
    if pathname != '/' and not data_clientes and not data_franquias:
        return upload_component

    if pathname == '/clientes':
        return clientes.layout
    elif pathname == '/franquias':
        return franquias.layout
    elif pathname == '/selecao':
        # --- LÓGICA DE SELEÇÃO DINÂMICA ---
        botoes = []
        if data_clientes:
            botoes.append(dbc.Col(dbc.Button("Análise de Clientes", href="/clientes", size="lg", className="w-100", color="primary")))
        if data_franquias:
            botoes.append(dbc.Col(dbc.Button("Análise de Franquias", href="/franquias", size="lg", className="w-100", color="success")))
        
        if not botoes:
             return html.Div([dbc.Alert("Nenhuma análise pôde ser gerada com as colunas do seu arquivo.", color="danger")])

        return html.Div([
            html.Div([
                html.H2("Bem-vindo ao Painel de Análise!", className="display-4"),
                html.P("Seu arquivo foi processado. Agora, escolha qual dashboard você gostaria de visualizar:", className="lead"),
                html.Hr(className="my-2"),
                dbc.Row(botoes, justify="center", className="g-4 mt-3")
            ], className="h-100 p-5 bg-light border rounded-3")
        ], className="p-5")
    else: # Página inicial padrão
        return upload_component
    
    


# --- PONTO DE ENTRADA DA APLICAÇÃO ---
if __name__ == '__main__':
    app.run(debug=True)