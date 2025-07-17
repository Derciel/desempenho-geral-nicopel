# pages/clientes.py
import dash
from dash import dcc, html, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import io

# Importa a instância 'app' do arquivo app.py
from app import app

# Componente de Instruções
instrucoes_layout = dbc.Alert([
    html.H5("Instruções de Uso", className="alert-heading"),
    html.P("Para usar o painel, baixe o arquivo no Módulo de Faturamento/Consulta/Itens Faturados e siga os passos:"),
    html.Details([
        html.Summary('Clique para ver a lista de colunas necessárias'),
        html.Ul([
            html.Li(html.B(col)) for col in ["N° OS", "Categoria", "Descrição Item", "Data Emissao", "Cliente Faturamento",
                                             "Nome Fantasia", "R$ Total", "CNPJ Cliente", "Documento", "Qtde",
                                             "R$ CM Fat", "R$ Markup Fat", "Vendedor"]
        ])
    ])
], color="info")

# Layout do dashboard de clientes
layout = dbc.Row([
    dbc.Col([
        html.H3("Filtros de Clientes"),
        html.Label("Clientes:"),
        dcc.Dropdown(id='dropdown-clientes', multi=True, placeholder="Todos..."),
        html.Label("Vendedores da Última Compra:", className="mt-3"),
        dcc.Dropdown(id='dropdown-vendedores', multi=True, placeholder="Todos..."),
        html.Hr(),
        dbc.Button("Baixar Relatório de Clientes", id="btn-download-clientes", color="primary", className="w-100 mb-2"),
        dbc.Button("Voltar ao Menu Principal", href="/", color="secondary", className="w-100"),
        dcc.Download(id="download-excel-clientes")
    ], width=12, lg=3, style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '5px'}),
    
    dbc.Col(dcc.Loading(html.Div(id='content-clientes')), width=12, lg=9)
])

# Callback para popular os filtros
@app.callback(
    [Output('dropdown-clientes', 'options'),
     Output('dropdown-vendedores', 'options')],
    Input('store-dados-clientes', 'data')
)
def popula_filtros_clientes(json_data):
    if not json_data:
        return [], []
    df_analise = pd.read_json(json_data, orient='split')
    clientes_opcoes = [{'label': i, 'value': i} for i in sorted(df_analise['Nome Fantasia'].unique())]
    vendedores_opcoes = [{'label': i, 'value': i} for i in sorted(df_analise['Vendedor da Ultima Compra'].unique())]
    return clientes_opcoes, vendedores_opcoes

# Callback para atualizar o conteúdo da página de clientes
@app.callback(
    Output('content-clientes', 'children'),
    [Input('dropdown-clientes', 'value'),
     Input('dropdown-vendedores', 'value')],
    State('store-dados-clientes', 'data')
)
def atualiza_dash_clientes(clientes, vendedores, json_data):
    if not json_data:
        return dbc.Alert("Dados não encontrados. Volte à página inicial e carregue o arquivo.", color="danger")

    df_analise = pd.read_json(json_data, orient='split')
    df_analise['Ultima Compra'] = pd.to_datetime(df_analise['Ultima Compra'])
    
    df_filtrado = df_analise.copy()
    if clientes:
        df_filtrado = df_filtrado[df_filtrado['Nome Fantasia'].isin(clientes)]
    if vendedores:
        df_filtrado = df_filtrado[df_filtrado['Vendedor da Ultima Compra'].isin(vendedores)]

    if df_filtrado.empty:
        return dbc.Alert("Nenhum dado encontrado para os filtros selecionados.", color="warning", className="mt-4")
        
    # Prepara os dataframes para as abas
    df_recencia_filtrado = df_filtrado.sort_values('Dias Sem Comprar', ascending=False)
    df_clientes_maior_50k = df_filtrado[df_filtrado['Faturamento Total'] >= 50000].sort_values('Faturamento Total', ascending=False)
    df_clientes_menor_50k = df_filtrado[df_filtrado['Faturamento Total'] < 50000].sort_values('Faturamento Total', ascending=False)
    
    # Prepara os dados para o gráfico da Visão Geral
    total_geral = df_filtrado['Faturamento Total'].sum()
    top_clientes = df_filtrado.nlargest(10, 'Faturamento Total')
    fig_rank = px.bar(top_clientes, x='Faturamento Total', y='Nome Fantasia', orientation='h', title='Top 10 Clientes por Faturamento', template='plotly_white').update_yaxes(categoryorder="total ascending")

    # Retorna o layout com abas
    return dcc.Tabs([
        dcc.Tab(label='Visão Geral', children=html.Div(className="p-4", children=[
            dbc.Row([
                dbc.Col(dbc.Card([dbc.CardBody([html.H4("Faturamento Total (Filtrado)"), html.P(f"R$ {total_geral:,.2f}")])])),
                dbc.Col(dbc.Card(dbc.CardBody([html.H4("Clientes na Análise"), html.P(df_filtrado['Nome Fantasia'].nunique())]))),
            ], className="mb-4 g-4"),
            dcc.Graph(figure=fig_rank)
        ])),
        dcc.Tab(label='Clientes >= 50k', children=html.Div(className="p-4", children=[
            html.H4("Clientes com Faturamento Acima de R$ 50.000"),
            dash_table.DataTable(
                data=df_clientes_maior_50k.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in df_clientes_maior_50k.columns],
                page_size=15, sort_action='native', filter_action='native', style_table={'overflowX': 'auto'}
            )
        ])),
        dcc.Tab(label='Clientes < 50k', children=html.Div(className="p-4", children=[
            html.H4("Clientes com Faturamento Abaixo de R$ 50.000"),
            dash_table.DataTable(
                data=df_clientes_menor_50k.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in df_clientes_menor_50k.columns],
                page_size=15, sort_action='native', filter_action='native', style_table={'overflowX': 'auto'}
            )
        ]))
    ])

# NOVO CALLBACK PARA O DOWNLOAD DO EXCEL DE CLIENTES
@app.callback(
    Output("download-excel-clientes", "data"),
    Input("btn-download-clientes", "n_clicks"),
    [State('store-dados-clientes', 'data'),
     State('dropdown-clientes', 'value'),
     State('dropdown-vendedores', 'value')],
    prevent_initial_call=True,
)
def gera_excel_clientes(n_clicks, json_data, clientes, vendedores):
    if not n_clicks or not json_data:
        raise dash.exceptions.PreventUpdate

    df_analise = pd.read_json(json_data, orient='split')
    df_analise['Ultima Compra'] = pd.to_datetime(df_analise['Ultima Compra'])
    
    df_filtrado = df_analise.copy()
    if clientes:
        df_filtrado = df_filtrado[df_filtrado['Nome Fantasia'].isin(clientes)]
    if vendedores:
        df_filtrado = df_filtrado[df_filtrado['Vendedor da Ultima Compra'].isin(vendedores)]

    if df_filtrado.empty:
        raise dash.exceptions.PreventUpdate

    # Prepara os relatórios para o Excel
    df_recencia_filtrado = df_filtrado.sort_values('Dias Sem Comprar', ascending=False)
    df_clientes_maior_50k = df_filtrado[df_filtrado['Faturamento Total'] >= 50000].sort_values('Faturamento Total', ascending=False)
    df_clientes_menor_50k = df_filtrado[df_filtrado['Faturamento Total'] < 50000].sort_values('Faturamento Total', ascending=False)
    
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        df_recencia_filtrado.to_excel(writer, sheet_name='Relatorio_Geral_Filtrado', index=False)
        df_clientes_maior_50k.to_excel(writer, sheet_name='Clientes_Acima_50k', index=False)
        df_clientes_menor_50k.to_excel(writer, sheet_name='Clientes_Abaixo_50k', index=False)

    return dcc.send_bytes(output_buffer.getvalue(), "Relatorio_Analise_Clientes.xlsx")