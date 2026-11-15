"""Thème visuel : palette bleu / vert neutre."""
import streamlit as st

BLUE, GREEN, TEAL, DARK = "#2E86AB", "#1B998B", "#0E7C86", "#0B4F6C"

CSS = f"""
<style>
.stApp {{ background: #F4F8F9; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {DARK} 0%, {TEAL} 100%); }}
[data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] .stButton button {{
    background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.45);
}}
.app-header {{
    background: linear-gradient(90deg, {DARK} 0%, {BLUE} 55%, {GREEN} 100%);
    padding: 1.2rem 1.6rem; border-radius: 14px; margin-bottom: 1.2rem;
    box-shadow: 0 4px 14px rgba(14,124,134,.25);
}}
.app-header h1 {{ color: #fff; margin: 0; font-size: 1.7rem; padding: 0; }}
.app-header p  {{ color: #E3F4F1; margin: .25rem 0 0 0; }}
[data-testid="stMetric"] {{
    background: #FFFFFF; border: 1px solid #D5E6E9; border-left: 5px solid {GREEN};
    border-radius: 12px; padding: .8rem 1rem; box-shadow: 0 2px 8px rgba(11,79,108,.07);
}}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: #FFFFFF; border-radius: 12px; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="app-header"><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)
