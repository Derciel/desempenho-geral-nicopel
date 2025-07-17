# app.py
import dash
import dash_bootstrap_components as dbc

# Inicializa a aplicação Dash. Esta instância 'app' será importada por outros arquivos.
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LITERA], suppress_callback_exceptions=True)
server = app.server