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
            dbc.Row([
                dbc.Col([
                    html.H1("ETF Performance Comparison", className="mb-4"),
                ], width=10),
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button(
                            "☰ Controls",
                            id="toggle-sidebar-btn",
                            color="secondary",
                            size="sm",
                            className="me-1"
                        ),
                        dbc.Button(
                            "📊 Legend",
                            id="toggle-legend-btn",
                            color="secondary",
                            size="sm"
                        ),
                    ], className="mt-2")
                ], width=2, className="text-end")
            ]),
            html.Hr(),
        ], width=12)
    ]),
    
    dbc.Row([
        # Left sidebar - Controls (with show/hide)
        dbc.Col([
            html.Div(id='sidebar-content', children=[
                html.H4("Controls", className="mb-3"),
                
                # Period selector
                html.Label("Time Period:", className="fw-bold"),
                dcc.Dropdown(
                    id='period-selector',
                    options=PERIOD_OPTIONS,
                    value='7d',  # Default value
                    className="mb-3"
                ),
                
                html.Hr(),
                
                # Group toggles
                dbc.Row([
                    dbc.Col([
                        html.Label("Show/Hide Groups:", className="fw-bold mb-2"),
                    ], width=8),
                    dbc.Col([
                        dbc.Button(
                            "Invert",
                            id="invert-groups-btn",
                            color="outline-secondary",
                            size="sm",
                            className="mb-2"
                        ),
                    ], width=4, className="text-end")
                ]),
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
            ])
        ], id='sidebar-col', width=3, className="border-end"),
        
        # Main chart area
        dbc.Col([
            dcc.Graph(id='etf-chart', style={'height': '80vh'}),
            html.Div(id='chart-info', className="mt-2 text-muted")
        ], id='chart-col', width=9)
    ]),
    
    # Store for browser session
    dcc.Store(id='session-store', storage_type='session', data={'period': '7d', 'visible_groups': list(groups.keys())}),
    dcc.Store(id='ui-state-store', storage_type='session', data={'show_sidebar': True, 'show_legend': True}),
    
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
    Output('session-store', 'data', allow_duplicate=True),
    Input('invert-groups-btn', 'n_clicks'),
    State('session-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def invert_group_selection(invert_clicks, session_data):
    """Invert the group selection when invert button is clicked"""
    if invert_clicks is None:
        return session_data
    
    # Get current visible groups
    if session_data and 'visible_groups' in session_data:
        current_visible = set(session_data['visible_groups'])
    else:
        current_visible = set(groups.keys())  # Default: all selected
    
    # Invert: selected becomes unselected, unselected becomes selected
    all_groups = set(groups.keys())
    new_visible = list(all_groups - current_visible)
    
    # Update session data
    if session_data is None:
        session_data = {}
    session_data['visible_groups'] = new_visible
    
    return session_data




@app.callback(
    Output('period-selector', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def restore_period_from_session(session_data):
    """Restore period selector value from session storage"""
    if session_data and 'period' in session_data:
        return session_data['period']
    return '7d'


@app.callback(
    Output('group-checkboxes', 'children'),
    Input('session-store', 'data')
)
def update_group_checkboxes(session_data):
    """Initialize group checkboxes, restore from session if available"""
    # Get visible groups from session store, or default to all
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
    Output('sidebar-col', 'style'),
    Output('chart-col', 'width'),
    Output('ui-state-store', 'data'),
    Input('toggle-sidebar-btn', 'n_clicks'),
    Input('toggle-legend-btn', 'n_clicks'),
    State('ui-state-store', 'data')
)
def toggle_ui_elements(sidebar_clicks, legend_clicks, ui_state):
    """Toggle sidebar and legend visibility"""
    if ui_state is None:
        ui_state = {'show_sidebar': True, 'show_legend': True}
    
    show_sidebar = ui_state.get('show_sidebar', True)
    show_legend = ui_state.get('show_legend', True)
    
    # Get which button was clicked
    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == 'toggle-sidebar-btn' and sidebar_clicks:
            show_sidebar = not show_sidebar
        elif trigger_id == 'toggle-legend-btn' and legend_clicks:
            show_legend = not show_legend
    
    ui_state['show_sidebar'] = show_sidebar
    ui_state['show_legend'] = show_legend
    
    # Determine sidebar style and chart width
    if show_sidebar:
        sidebar_style = {'display': 'block'}
        chart_width = 9
    else:
        sidebar_style = {'display': 'none'}
        chart_width = 12
    
    return sidebar_style, chart_width, ui_state


@app.callback(
    Output('session-store', 'data'),
    Output('etf-chart', 'figure'),
    Output('error-display', 'children'),
    Output('chart-info', 'children'),
    Input('period-selector', 'value'),
    Input({'type': 'group-checkbox', 'index': ALL}, 'value'),
    Input('ui-state-store', 'data'),
    State('session-store', 'data'),
    State({'type': 'group-checkbox', 'index': ALL}, 'id')
)
def update_chart(period, group_values, ui_state, session_data, group_ids):
    """Update chart based on period and group selections"""
    # Initialize session data if it doesn't exist
    if session_data is None:
        session_data = {'period': '7d', 'visible_groups': list(groups.keys())}
    
    # Initialize UI state
    if ui_state is None:
        ui_state = {'show_sidebar': True, 'show_legend': True}
    
    # Get legend visibility from UI state
    show_legend = ui_state.get('show_legend', True)
    
    # Get context to check what triggered this callback
    ctx = callback_context
    period_triggered = ctx.triggered and any(
        'period-selector' in prop_id for prop_id in [t['prop_id'] for t in ctx.triggered]
    )
    
    # Handle period: restore from session store on initial load, save when user changes it
    if period_triggered:
        # User changed the period selector - save it
        session_data['period'] = period
    elif 'period' in session_data:
        # Restore period from session store (on page reload)
        period = session_data['period']
    else:
        # First time, save the current period
        session_data['period'] = period
    
    # Get visible groups from checkboxes (user interaction)
    visible_groups_from_checkboxes = []
    if group_values and group_ids:
        for idx, group_id in enumerate(group_ids):
            if idx < len(group_values) and group_values[idx]:  # If checkbox is checked
                visible_groups_from_checkboxes.append(group_id['index'])
    
    # Determine which groups to use:
    # Priority: session store (if exists) > checkboxes > default to all
    # This ensures that on page reload, we restore from session store
    ctx = callback_context
    checkbox_triggered = ctx.triggered and any(
        'group-checkbox' in prop_id for prop_id in [t['prop_id'] for t in ctx.triggered]
    )
    
    if checkbox_triggered and visible_groups_from_checkboxes:
        # User just changed checkboxes - use their selection
        visible_groups = visible_groups_from_checkboxes
    elif session_data and 'visible_groups' in session_data:
        # Restore from session store (on page reload or initial load with saved data)
        visible_groups = session_data['visible_groups']
    elif visible_groups_from_checkboxes:
        # Use checkbox values if available
        visible_groups = visible_groups_from_checkboxes
    else:
        # Default: show all groups
        visible_groups = list(groups.keys())
    
    # Always update session store with current selection
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
            
            line_color = colors[color_idx % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['pct_change'],
                mode='lines',
                name=f"{ticker} - {name}",
                line=dict(color=line_color, width=2),
                hovertemplate=f'<b>{ticker}</b><br>' +
                             f'{name}<br>' +
                             'Date: %{x}<br>' +
                             'Change: %{y:.2f}%<extra></extra>',
                hoverlabel=dict(
                    bgcolor='white',
                    bordercolor=line_color,
                    font=dict(color='blue', size=12)
                )
            ))
            color_idx += 1
    
    # Update layout
    period_label = next((opt['label'] for opt in PERIOD_OPTIONS if opt['value'] == period), period)
    
    # Get legend visibility from UI state
    show_legend = ui_state.get('show_legend', True) if ui_state else True
    
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
        ) if show_legend else None,
        margin=dict(r=200 if show_legend else 50),
        height=600,
        showlegend=show_legend
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
