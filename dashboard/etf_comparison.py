"""
Interactive ETF Comparison Dashboard
Dash web application with browser session storage
"""
import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import plotly.graph_objs as go
import plotly.express as px
from core.etf_data_fetcher import ETFDataFetcher
import dash_bootstrap_components as dbc
from datetime import datetime
import pandas as pd


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
    {'label': '3 Years', 'value': '3y'},
    {'label': '20 Years', 'value': '20y'}
]

# Shared group color map (same order as bar chart "Group color" mode)
GROUP_PALETTE = px.colors.qualitative.Set1


def get_group_colors():
    """Deterministic group -> color for sidebar and bar chart."""
    return {g: GROUP_PALETTE[i % len(GROUP_PALETTE)] for i, g in enumerate(sorted(groups.keys()))}

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
                html.Label("SMA (0 = real close, 1–730 = SMA days):", className="fw-bold mt-2"),
                dcc.Slider(
                    id='sma-days',
                    min=0,
                    max=730,
                    step=1,
                    value=0,
                    marks={0: '0', 50: '50', 100: '100', 200: '200', 365: '365', 730: '730'},
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
                html.Div(id='sma-days-value', className="small text-muted mb-2"),
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
                html.Label("Chart color (line + bar):", className="fw-bold"),
                dcc.Dropdown(
                    id='bar-color-mode',
                    options=[
                        {'label': 'Profit / Loss (green / red)', 'value': 'pnl'},
                        {'label': 'Group color', 'value': 'group'},
                        {'label': 'Item color (per ETF)', 'value': 'item'},
                    ],
                    value='pnl',
                    clearable=False,
                    className="mb-2"
                ),
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
            dcc.Graph(id='etf-chart', style={'height': '65vh'}),
            html.Div(id='chart-info', className="mt-2 text-muted"),
            html.Hr(),
            dcc.Graph(id='pnl-bar-chart', style={'height': '50vh'}),
            html.Div(id='period-summary', className="mt-2 text-muted"),
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
    prevent_initial_call=True
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
    prevent_initial_call=True
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
    """Initialize group checkboxes, restore from session if available. Show group name with color dot."""
    if session_data and 'visible_groups' in session_data:
        visible_groups = session_data['visible_groups']
    else:
        visible_groups = list(groups.keys())
    group_colors = get_group_colors()
    out = []
    for group_name in sorted(groups.keys()):
        color = group_colors.get(group_name, "#888")
        dot = html.Span(
            title=group_name,
            style={
                "display": "inline-block",
                "width": 10,
                "height": 10,
                "borderRadius": "50%",
                "backgroundColor": color,
                "marginRight": 8,
                "verticalAlign": "middle",
                "flexShrink": 0,
            },
        )
        out.append(
            html.Div(
                [
                    dot,
                    dbc.Checklist(
                        options=[{"label": group_name, "value": group_name}],
                        value=[group_name] if group_name in visible_groups else [],
                        id={"type": "group-checkbox", "index": group_name},
                        className="mb-2",
                        style={"display": "inline-block", "verticalAlign": "middle"},
                    ),
                ],
                className="mb-2",
                style={"display": "flex", "alignItems": "center"},
            )
        )
    return html.Div(out)


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
    Output('sma-days-value', 'children'),
    Input('sma-days', 'value')
)
def display_sma_value(sma_days):
    """Show current SMA setting."""
    if sma_days is None or sma_days == 0:
        return "0 = real close"
    return f"SMA{sma_days}"

@app.callback(
    Output('session-store', 'data'),
    Output('etf-chart', 'figure'),
    Output('pnl-bar-chart', 'figure'),
    Output('period-summary', 'children'),
    Output('error-display', 'children'),
    Output('chart-info', 'children'),
    Input('period-selector', 'value'),
    Input('sma-days', 'value'),
    Input({'type': 'group-checkbox', 'index': ALL}, 'value'),
    Input('bar-color-mode', 'value'),
    Input('ui-state-store', 'data'),
    State('session-store', 'data'),
    State({'type': 'group-checkbox', 'index': ALL}, 'id')
)
def update_chart(period, sma_days, group_values, bar_color_mode, ui_state, session_data, group_ids):
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
        empty_bar = go.Figure()
        empty_bar.update_layout(xaxis_title="", yaxis_title="% change")
        return session_data, empty_fig, empty_bar, "", html.Div(), ""

    # Fetch data
    data_results, errors = fetcher.fetch_data(period=period, tickers=visible_tickers)
    sma_days = int(sma_days) if sma_days is not None else 0

    def pct_series_for_df(df):
        """Return pct_change series: real close if sma_days==0, else from SMA(sma_days) of Close."""
        close = df['Close']
        if sma_days <= 0:
            return df['pct_change']
        smooth = close.rolling(window=sma_days, min_periods=1).mean()
        first = smooth.iloc[0]
        if first == 0:
            return df['pct_change']
        return ((smooth - first) / first) * 100.0

    # Build single list of tickers we actually have data for (sync line chart and bar chart)
    chart_tickers = []
    for ticker in visible_tickers:
        if ticker not in data_results:
            continue
        df = data_results[ticker]
        if df.empty or 'pct_change' not in df.columns:
            continue
        info = fetcher.get_ticker_info(ticker) or {}
        name = info.get('name', ticker)
        group = info.get('group', '')
        total_pct = float(df['pct_change'].iloc[-1]) if len(df) else 0.0
        chart_tickers.append((ticker, df, name, group, total_pct))

    group_to_color = get_group_colors()
    line_colors = px.colors.qualitative.Set3
    mode = bar_color_mode or 'pnl'

    fig = go.Figure()
    ticker_to_item_color = {}
    for idx, (ticker, df, name, group, total_pct) in enumerate(chart_tickers):
        item_color = line_colors[idx % len(line_colors)]
        ticker_to_item_color[ticker] = item_color
        if mode == 'pnl':
            line_color = "#0B6E4F" if total_pct >= 0 else "#B00020"
        elif mode == 'group':
            line_color = group_to_color.get(group, "#888")
        else:
            line_color = item_color

        pct_series = pct_series_for_df(df)
        fig.add_trace(go.Scatter(
            x=df.index.tolist(),
            y=pct_series.tolist(),
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

    # Update layout
    period_label = next((opt['label'] for opt in PERIOD_OPTIONS if opt['value'] == period), period)
    sma_suffix = f" (SMA{sma_days})" if sma_days > 0 else ""
    show_legend = ui_state.get('show_legend', True) if ui_state else True

    fig.update_layout(
        title=f'ETF Performance Comparison - {period_label}{sma_suffix}',
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
            x=1.02,
            font=dict(color='blue', size=12)
        ) if show_legend else None,
        margin=dict(r=200 if show_legend else 50),
        height=600,
        showlegend=show_legend
    )

    # Period return bar chart: same tickers as performance chart (sync show/hide)
    rows_pnl = []
    for ticker, df, name, group, total_pct in chart_tickers:
        rows_pnl.append({
            "ticker": ticker,
            "name": name,
            "group": group,
            "pct": total_pct,
            "item_color": ticker_to_item_color.get(ticker, "#888"),
            "group_color": group_to_color.get(group, "#888"),
        })
    rows_pnl.sort(key=lambda r: r["pct"], reverse=True)

    if rows_pnl:
        labels = [r["ticker"] for r in rows_pnl]
        names = [r["name"] for r in rows_pnl]
        pcts = [r["pct"] for r in rows_pnl]
        mode = bar_color_mode or 'pnl'
        if mode == 'pnl':
            bar_colors = ["#0B6E4F" if p >= 0 else "#B00020" for p in pcts]
        elif mode == 'group':
            bar_colors = [r["group_color"] for r in rows_pnl]
        else:
            bar_colors = [r["item_color"] for r in rows_pnl]
        pnl_fig = go.Figure(
            go.Bar(
                x=labels,
                y=pcts,
                customdata=names,
                marker_color=bar_colors,
                text=[f"{p:+.2f}%" for p in pcts],
                textposition="outside",
                hovertemplate="%{x} — %{customdata}<br>% change: %{y:.2f}%<extra></extra>",
            )
        )
        period_label_short = next((o["label"] for o in PERIOD_OPTIONS if o["value"] == period), period)
        # Colored x-axis labels via annotations (ticker text uses same color as bar)
        n_bars = len(labels)
        axis_annotations = [
            dict(
                x=i,
                y=-0.06,
                text=labels[i],
                showarrow=False,
                font=dict(size=11, color=bar_colors[i]),
                xref="x",
                yref="paper",
                yanchor="top",
                xanchor="center",
            )
            for i in range(n_bars)
        ]
        pnl_fig.update_layout(
            title=f"ETF % change — {period_label_short} (best → worst)",
            xaxis_title="",
            yaxis_title="% change",
            xaxis=dict(tickangle=-45, showticklabels=False),
            annotations=axis_annotations,
            margin=dict(b=80),
            height=400,
            showlegend=False,
        )
        # What's good in this range
        top = rows_pnl[:5]
        bottom = rows_pnl[-3:] if len(rows_pnl) >= 3 else []
        good = " • ".join([f"{r['ticker']} {r['pct']:+.1f}%" for r in top])
        weak = " • ".join([f"{r['ticker']} {r['pct']:+.1f}%" for r in bottom]) if bottom else ""
        period_summary = [
            html.Strong("Top in this range: "),
            good,
        ]
        if weak:
            period_summary.extend([html.Br(), html.Span("Weakest: ", className="text-muted"), weak])
        period_summary = html.Div(period_summary)
    else:
        pnl_fig = go.Figure()
        pnl_fig.update_layout(xaxis_title="", yaxis_title="% change")
        period_summary = ""

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
    info_text = f"Showing {len(chart_tickers)} ETFs from {len(visible_groups)} groups"
    if errors:
        info_text += f" ({len(errors)} errors)"

    return session_data, fig, pnl_fig, period_summary, html.Div(error_elements), info_text


if __name__ == '__main__':
    print(f"\n{'='*60}")
    print("ETF Comparison Dashboard")
    print(f"{'='*60}")
    print(f"Total ETFs: {len(all_tickers)}")
    print(f"Groups: {len(groups)}")
    print(f"\nStarting server...")
    print(f"Open http://127.0.0.1:8050 in your browser")
    print(f"{'='*60}\n")
    app.run(debug=True, host="0.0.0.0", port=8050)
