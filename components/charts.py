"""Graphiques Plotly (barres, radar, historique, équipe)."""
import plotly.graph_objects as go

C_AUTO, C_MGR = "#2E86AB", "#1B998B"


def _layout(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#12303A"), margin=dict(l=20, r=20, t=40, b=20),
                      legend=dict(orientation="h", y=-0.15))
    return fig


def _series(df):
    out = []
    for col, color in (("Auto", C_AUTO), ("Manager", C_MGR)):
        if col in df and df[col].notna().any():
            out.append((col, color))
    return out


def radar(df) -> go.Figure:
    fig = go.Figure()
    labels = list(df["Critère"])
    for col, color in _series(df):
        vals = [0 if v != v else v for v in df[col]]
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=labels + labels[:1], name=col,
                                      fill="toself", opacity=0.55, line=dict(color=color, width=2)))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5], tickvals=[1, 2, 3, 4, 5])))
    return _layout(fig, 460)


def grouped_bar(df) -> go.Figure:
    fig = go.Figure()
    for col, color in _series(df):
        fig.add_trace(go.Bar(x=df["Critère"], y=df[col], name=col, marker_color=color,
                             text=df[col], textposition="outside"))
    fig.update_layout(barmode="group", yaxis=dict(range=[0, 5.5], title="Note /5"))
    return _layout(fig)


def history_line(df) -> go.Figure:
    fig = go.Figure()
    for col, color in _series(df):
        fig.add_trace(go.Scatter(x=df["Période"], y=df[col], name=col, mode="lines+markers",
                                 line=dict(color=color, width=3), marker=dict(size=9)))
    fig.update_layout(yaxis=dict(range=[0, 5.2], title="Score final /5"),
                      xaxis=dict(type="category", title="Période"))
    return _layout(fig, 380)


def team_bar(df) -> go.Figure:
    fig = go.Figure()
    for col, color in _series(df):
        fig.add_trace(go.Bar(x=df["Collaborateur"], y=df[col], name=col, marker_color=color))
    fig.update_layout(barmode="group", yaxis=dict(range=[0, 5.2], title="Score final /5"))
    return _layout(fig, 380)
