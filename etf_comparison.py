"""
Interactive ETF Comparison Dashboard
Dash web application with browser session storage
"""
import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import plotly.graph_objs as go
import plotly.express as px
from etf_data_fetcher import ETFDataFetcher
import dash_bootstrap_components as dbc
from datetime import datetime


# Initialize data fetcher
fetcher = ETFDataFetcher()

# Get all tickers and groups
all_tickers = list(fetcher.tickers_map.keys())
groups = fetcher.get_tickers_by_group()

# Initialize Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define period options
PERIOD_OPTIONS = [
    {'label': '7 Days', 'value': '7d'},
    {'label': '1 Month', 'value': '1m'},
    {'label': '6 Months', 'value': '6m'},
    {'label': '1 Year', 'value': '1y'},
    {'label': '3 Years', 'value': '3y'}
]

# App layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("ETF Performance Comparison", className="mb-4"),
            html.Hr(),
        ], width=12)
    ]),
    
    dbc.Row([
        # Left sidebar - Controls
        dbc.Col([
            html.H4("Controls", className="mb-3"),
            
            # Period selector
            html.Label("Time Period:", className="fw-bold"),
            dcc.Dropdown(
                id='period-selector',
                options=PERIOD_OPTIONS,
                value='7d',  # Default to 7 days
                className="mb-3"
            ),
            
            html.Hr(),
            
            # Group toggles
            html.Label("Show/Hide Groups:", className="fw-bold mb-2"),
            html.Div(id='group-checkboxes'),
            
            html.Hr(),
            
            # Error display
            html.Div(id='error-display', className="mt-3"),
            
            # Loading indicator
            dcc.Loading(
                id="loading",
                type="default",
                children=html.Div(id="loading-output")
            ),
            
        ], width=3, className="border-end"),
        
        # Main chart area
        dbc.Col([
            dcc.Graph(id='etf-chart', style={'height': '80vh'}),
            html.Div(id='chart-info', className="mt-2 text-muted")
        ], width=9)
    ]),
    
    # Store for browser session
    dcc.Store(id='session-store', storage_type='session'),
    
], fluid=True)


def create_group_checkboxes():
    """Create checkboxes for each group"""
    checkboxes = []
    for group_name in sorted(groups.keys()):
        checkboxes.append(
            dbc.Checklist(
                options=[{'label': group_name, 'value': group_name}],
                value=[group_name],  # All checked by default
                id={'type': 'group-checkbox', 'index': group_name},
                className="mb-2"
            )
        )
    return html.Div(checkboxes)


@app.callback(
    Output('group-checkboxes', 'children'),
    Input('session-store', 'data')
)
def update_group_checkboxes(session_data):
    """Initialize group checkboxes, restore from session if available"""
    if session_data and 'visible_groups' in session_data:
        visible_groups = session_data['visible_groups']
    else:
        visible_groups = list(groups.keys())  # All visible by default
    
    checkboxes = []
    for group_name in sorted(groups.keys()):
        checkboxes.append(
            dbc.Checklist(
                options=[{'label': group_name, 'value': group_name}],
                value=[group_name] if group_name in visible_groups else [],
                id={'type': 'group-checkbox', 'index': group_name},
                className="mb-2"
            )
        )
    return html.Div(checkboxes)


@app.callback(
    Output('session-store', 'data'),
    Output('etf-chart', 'figure'),
    Output('error-display', 'children'),
    Output('chart-info', 'children'),
    Input('period-selector', 'value'),
    Input({'type': 'group-checkbox', 'index': ALL}, 'value'),
    State('session-store', 'data'),
    State({'type': 'group-checkbox', 'index': ALL}, 'id')
)
def update_chart(period, group_values, session_data, group_ids):
    """Update chart based on period and group selections"""
    # Initialize session data
    if session_data is None:
        session_data = {'period': '7d', 'visible_groups': list(groups.keys())}
    
    # Update session data
    session_data['period'] = period
    
    # Get visible groups from checkboxes
    visible_groups = []
    if group_values and group_ids:
        for idx, group_id in enumerate(group_ids):
            if idx < len(group_values) and group_values[idx]:  # If checkbox is checked
                visible_groups.append(group_id['index'])
    
    # If no groups selected (initial load), show all
    if not visible_groups:
        visible_groups = list(groups.keys())
    
    session_data['visible_groups'] = visible_groups
    
    # Get tickers for visible groups
    visible_tickers = []
    for group in visible_groups:
        visible_tickers.extend(groups.get(group, []))
    
    if not visible_tickers:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="No ETFs selected",
            xaxis_title="Date",
            yaxis_title="Percentage Change (%)"
        )
        return session_data, empty_fig, html.Div(), ""
    
    # Fetch data
    data_results, errors = fetcher.fetch_data(period=period, tickers=visible_tickers)
    
    # Create figure
    fig = go.Figure()
    
    # Add traces for each ticker
    colors = px.colors.qualitative.Set3
    color_idx = 0
    
    for ticker in visible_tickers:
        if ticker in data_results:
            df = data_results[ticker]
            ticker_info = fetcher.get_ticker_info(ticker)
            name = ticker_info['name'] if ticker_info else ticker
            
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['pct_change'],
                mode='lines',
                name=f"{ticker} - {name}",
                line=dict(color=colors[color_idx % len(colors)], width=2),
                hovertemplate=f'<b>{ticker}</b><br>' +
                             f'{name}<br>' +
                             'Date: %{x}<br>' +
                             'Change: %{y:.2f}%<extra></extra>',
                hoverlabel=dict(
                    bgcolor='white',
                    bordercolor='red',
                    font=dict(color='blue', size=12)
                )
            ))
            color_idx += 1
    
    # Update layout
    period_label = next((opt['label'] for opt in PERIOD_OPTIONS if opt['value'] == period), period)
    fig.update_layout(
        title=f'ETF Performance Comparison - {period_label}',
        xaxis_title='Date',
        yaxis_title='Percentage Change (%)',
        hovermode='closest',
        hoverlabel=dict(
            bgcolor='white',
            bordercolor='black',
            font=dict(color='black', size=12)
        ),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        margin=dict(r=200),
        height=600
    )
    
    # Error display
    error_elements = []
    if errors:
        error_elements.append(html.H5("Errors:", className="text-danger mt-3"))
        for ticker, error_msg in errors.items():
            ticker_info = fetcher.get_ticker_info(ticker)
            name = ticker_info['name'] if ticker_info else ticker
            error_elements.append(
                html.Div([
                    html.Strong(f"{ticker} ({name}): "),
                    html.Span(error_msg, className="text-danger")
                ], className="mb-1")
            )
    
    # Chart info
    info_text = f"Showing {len(data_results)} ETFs from {len(visible_groups)} groups"
    if errors:
        info_text += f" ({len(errors)} errors)"
    
    return session_data, fig, html.Div(error_elements), info_text


if __name__ == '__main__':
    print(f"\n{'='*60}")
    print("ETF Comparison Dashboard")
    print(f"{'='*60}")
    print(f"Total ETFs: {len(all_tickers)}")
    print(f"Groups: {len(groups)}")
    print(f"\nStarting server...")
    print(f"Open http://127.0.0.1:8050 in your browser")
    print(f"{'='*60}\n")
    
    app.run(debug=True, port=8050)
