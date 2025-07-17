# pages/franquias.py
import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import io

# Importa a instância 'app' do arquivo app.py
from app import app

# Constantes específicas deste dashboard
CATEGORIAS_EXCLUIR = ['CAIXA SORVETE/AÇAI', 'CAIXA DE PIZZA']

# Layout do dashboard de franquias
layout = dbc.Row([
    dbc.Col([
        html.H3("Filtros de Franquias"),
        html.Label("Franquias:"),
        dcc.Dropdown(id='dropdown-franquias-main', multi=True, placeholder="Selecione..."),
        html.Label("Itens (Opcional):", className="mt-3"),
        dcc.Dropdown(id='dropdown-itens-main', multi=True, placeholder="Selecione..."),
        html.Hr(),
        dbc.Button("Voltar ao Menu Principal", href="/", color="secondary", className="w-100 mb-2"),
        # Adiciona o botão de download e o componente de download
        dbc.Button("Baixar Relatório em Excel", id="btn-download-franquias", color="primary", className="w-100"),
        dcc.Download(id="download-excel-franquias")
    ], width=12, lg=3, style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '5px'}),
    
    dbc.Col(dcc.Loading(html.Div(id='dashboard-franquias-content')), width=12, lg=9)
])

# Callback para popular os filtros
@app.callback(
    [Output('dropdown-franquias-main', 'options'),
     Output('dropdown-itens-main', 'options')],
    Input('store-dados-franquias', 'data')
)
def popula_filtros_franquias(json_data):
    if not json_data:
        return [], []
    df_franquias = pd.read_json(json_data, orient='split')
    # CORREÇÃO: Transforma a lista de strings em uma lista de dicionários para o Dropdown
    franquias_opcoes = [{'label': i, 'value': i} for i in sorted(df_franquias['FRANQUIA'].unique())]
    itens_opcoes = [{'label': i, 'value': i} for i in sorted(df_franquias['Descrição Item'].unique())]
    return franquias_opcoes, itens_opcoes

# Callback para atualizar o conteúdo da página de franquias
@app.callback(
    Output('dashboard-franquias-content', 'children'),
    [Input('dropdown-franquias-main', 'value'),
     Input('dropdown-itens-main', 'value')],
    State('store-dados-franquias', 'data')
)
def atualiza_dash_franquias(franquias, itens, json_data):
    if not json_data or not franquias:
        return dbc.Alert("Selecione uma ou mais franquias para começar a análise.", color="info", className="mt-4")
    
    df_franquias = pd.read_json(json_data, orient='split')
    df_franquias['Data Emissao'] = pd.to_datetime(df_franquias['Data Emissao'])
    
    # Aplica filtros
    df_filtrado = df_franquias[df_franquias['FRANQUIA'].isin(franquias)]
    if itens:
        df_filtrado = df_filtrado[df_filtrado['Descrição Item'].isin(itens)]
        
    regex = '|'.join(CATEGORIAS_EXCLUIR)
    df_filtrado = df_filtrado[~df_filtrado['Categoria'].str.contains(regex, case=False, na=False)]

    if df_filtrado.empty:
        return dbc.Alert("Nenhum dado encontrado para os filtros selecionados.", color="warning", className="mt-4")

    # --- CÁLCULOS PARA OS GRÁFICOS ---
    total_por_franquia = df_filtrado.groupby('FRANQUIA')['R$ Total'].sum().sort_values(ascending=False).reset_index()
    faturamento_semanal = df_filtrado.set_index('Data Emissao').groupby('FRANQUIA').resample('W-MON').agg({'R$ Total': 'sum'}).reset_index()
    top_categorias = df_filtrado.groupby('Categoria')['R$ Total'].sum().nlargest(4).reset_index()
    top_vendedores = df_filtrado.groupby('Vendedor')['R$ Total'].sum().nlargest(10).reset_index()

    # --- CRIAÇÃO DOS GRÁFICOS ---
    fig_rank = px.bar(total_por_franquia, x='R$ Total', y='FRANQUIA', orientation='h', title='Ranking de Faturamento Total', template='plotly_white').update_layout(yaxis={'categoryorder':'total ascending'}, title_x=0.5)
    fig_semanal = px.line(faturamento_semanal, x='Data Emissao', y='R$ Total', color='FRANQUIA', title='Desempenho Semanal', template='plotly_white', markers=True).update_layout(title_x=0.5)
    fig_categorias = px.pie(top_categorias, values='R$ Total', names='Categoria', title='Top 4 Categorias', hole=.3, template='plotly_white').update_layout(title_x=0.5)
    fig_vendedores = px.bar(top_vendedores, x='R$ Total', y='Vendedor', orientation='h', title='Top 10 Vendedores', template='plotly_white').update_layout(yaxis={'categoryorder':'total ascending'}, title_x=0.5)
    
    # --- MONTAGEM DO LAYOUT DO DASHBOARD ---
    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Faturamento Total (Filtrado)"), html.H4(f"R$ {df_filtrado['R$ Total'].sum():,.2f}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Franquias na Análise"), html.H4(len(franquias))]))),
        ], className="mb-4 g-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_rank), width=12, lg=6, className="mb-4"),
            dbc.Col(dcc.Graph(figure=fig_semanal), width=12, lg=6, className="mb-4"),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_categorias), width=12, lg=6, className="mb-4"),
            dbc.Col(dcc.Graph(figure=fig_vendedores), width=12, lg=6, className="mb-4"),
        ])
    ])

# --- NOVO CALLBACK PARA DOWNLOAD ---
@app.callback(
    Output("download-excel-franquias", "data"),
    Input("btn-download-franquias", "n_clicks"),
    [State('store-dados-franquias', 'data'),
     State('dropdown-franquias-main', 'value'),
     State('dropdown-itens-main', 'value')],
    prevent_initial_call=True,
)
def gera_excel_franquias(n_clicks, json_data, franquias, itens):
    if not n_clicks or not json_data or not franquias:
        raise dash.exceptions.PreventUpdate

    df_franquias = pd.read_json(json_data, orient='split')
    df_franquias['Data Emissao'] = pd.to_datetime(df_franquias['Data Emissao'])
    
    # Replica a mesma lógica de filtros do dashboard
    df_filtrado = df_franquias[df_franquias['FRANQUIA'].isin(franquias)]
    if itens:
        df_filtrado = df_filtrado[df_filtrado['Descrição Item'].isin(itens)]
    regex = '|'.join(CATEGORIAS_EXCLUIR)
    df_final = df_filtrado[~df_filtrado['Categoria'].str.contains(regex, case=False, na=False)]

    if df_final.empty:
        raise dash.exceptions.PreventUpdate
    
    # Recalcula os resumos para exportação
    total_por_franquia = df_final.groupby('FRANQUIA')['R$ Total'].sum().sort_values(ascending=False).reset_index()
    faturamento_semanal = df_final.set_index('Data Emissao').groupby('FRANQUIA').resample('W-MON').agg({'R$ Total': 'sum'}).reset_index()
    top_categorias = df_final.groupby('Categoria')['R$ Total'].sum().nlargest(4).reset_index()
    top_vendedores = df_final.groupby('Vendedor')['R$ Total'].sum().nlargest(10).reset_index()

    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, sheet_name='Dados_Filtrados', index=False)
        total_por_franquia.to_excel(writer, sheet_name='Resumo_Total_Franquia', index=False)
        faturamento_semanal.to_excel(writer, sheet_name='Resumo_Semanal', index=False)
        top_categorias.to_excel(writer, sheet_name='Resumo_Categorias', index=False)
        top_vendedores.to_excel(writer, sheet_name='Resumo_Vendedores', index=False)
    
    return dcc.send_bytes(output_buffer.getvalue(), "Relatorio_Analitico_Franquias.xlsx")