"""Identidade visual e navegação. Sem dependências além do Streamlit."""
import streamlit as st


CSS = """
<style>
.stApp { background: #f3f6f8; }
.stMainBlockContainer { max-width: 1480px; padding: 2.5rem 3rem 4rem; }
[data-testid="stHeader"] { background: #f3f6f8; }
h1, h2, h3 { color: #172b3a; letter-spacing: -.025em; text-wrap: balance; }
h1 { font-size: 2rem !important; font-weight: 650 !important; padding-bottom: .35rem !important; }
h2 { font-size: 1.8rem !important; font-weight: 650 !important; }
h3 { font-size: 1.15rem !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #526675; }
.page-kicker { font-size: .75rem; letter-spacing: .12em; font-weight: 650; color: #526675; margin: 0 0 1.3rem; }
[data-testid="stSidebar"] { background: #fff; border-right: 1px solid #dce5e9; }
[data-testid="stSidebarUserContent"] { padding: 1.7rem 1.25rem; }
.brand { display: flex; align-items: center; gap: 12px; margin: 0 0 2rem; }
.brand-mark { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: #096b72; color: white; flex-shrink: 0; }
.brand-name { color: #172b3a; font-weight: 700; font-size: 1.3rem; letter-spacing: -.02em; }
.brand-note { color: #526675; font-size: .78rem; }
.nav-group { font-size: .68rem; line-height: 1.6; font-weight: 650; letter-spacing: .13em; color: #526675; margin: 0; padding: 14px 12px 8px; }
[data-testid="stSidebar"] [data-testid="stButton"] button {
    justify-content: flex-start; min-height: 46px; border-radius: 9px; padding: .65rem .85rem;
    border: 1px solid transparent; box-shadow: none; font-weight: 500;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] { background: transparent; color: #425969; }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover { background: #f1f6f7; color: #096b72; }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    background: #e4f2f1; color: #075d64; border-color: #c6e4e2; font-weight: 650;
    box-shadow: inset 3px 0 #096b72;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .35rem; }
.sidebar-footer { border-top: 1px solid #e2e9ed; margin-top: 2rem; padding: 1.1rem .75rem 0; color: #526675; font-size: .78rem; line-height: 1.6; }
.sidebar-footer strong { color: #172b3a; font-weight: 600; }
[data-testid="stMetric"] { background: transparent; border: 0; border-radius: 0; padding: .4rem 0; display: flex; flex-direction: column; }
[data-testid="stMetricLabel"] { color: #526675; order: 2; font-weight: 400; }
[data-testid="stMetricValue"] { color: #263238; font-size: 2rem; line-height: 1.3; font-weight: 600; font-variant-numeric: tabular-nums; order: 1; }
[class*="st-key-indicador_"] { padding: 0 1rem; }
[data-testid="stColumn"]:not(:first-child) [class*="st-key-indicador_"] { border-left: 1px solid #d5dde1; }
[data-testid="stForm"] { background: #fff; border: 1px solid #dce5e9; border-radius: 12px; padding: 1.5rem; }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #dce5e9; }
[data-testid="stTextInput"] input { min-height: 44px; }
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    border: 1px solid #bdcdd5; border-radius: 8px; background-color: #f8fafb;
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within {
    border-color: #096b72; box-shadow: 0 0 0 2px #d8eeed;
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button { border-radius: 9px; min-height: 42px; }
button:focus-visible, input:focus-visible { outline: 3px solid #218a93 !important; outline-offset: 3px; }
[data-baseweb="tab-list"] { gap: 1.5rem; border-bottom: 1px solid #dce5e9; margin-bottom: 1rem; }
[data-baseweb="tab"] { padding-bottom: .8rem; font-weight: 500; }
.st-key-painel_consulta { background: #fff; border: 1px solid #dce5e9; border-radius: 12px; padding: 1.5rem; margin-top: .7rem; }
.st-key-filtro_disponiveis { padding-top: 1.9rem; }
@media (max-width: 900px) {
    .stMainBlockContainer { padding: 2rem 1.25rem; }
    [data-testid="stMetric"] { padding: .4rem 0; }
}
@media (max-width: 640px) {
    h1 { font-size: 1.65rem !important; }
    .stMainBlockContainer { padding: 3rem 1rem 2rem; }
    .st-key-filtro_disponiveis { padding-top: 0; }
    .st-key-painel_consulta { padding: 1rem; }
    [data-testid="stColumn"]:not(:first-child) [class*="st-key-indicador_"] { border-left: 0; border-top: 1px solid #d5dde1; padding-top: .6rem; }
}
</style>
"""


def aplicar_visual():
    st.markdown(CSS, unsafe_allow_html=True)


def navegar(pagina):
    st.session_state['pagina_atual'] = pagina


def indicador(campo, rotulo, valor):
    """Número e rótulo, sem decoração ou conteúdo adicional."""
    with st.container(key=f'indicador_{campo}'):
        st.metric(rotulo, valor)


def navegacao():
    """Botões nativos: teclado, foco e eventos permanecem sob controle do Streamlit."""
    if 'pagina_atual' not in st.session_state:
        st.session_state['pagina_atual'] = 'Consulta de Livros'
    grupos = [
        ('BIBLIOTECA', [('Consulta de Livros', 'Acervo', 'auto_stories'),
                        ('Cadastro de Livros', 'Gerenciar livros', 'library_add'),
                        ('Cadastro de Usuários', 'Usuários', 'group')]),
        ('CIRCULAÇÃO', [('Empréstimo de Livros', 'Empréstimos', 'swap_horiz'),
                        ('Devolução de Livros', 'Devoluções', 'assignment_return')]),
        ('ACOMPANHAMENTO', [('Relatórios', 'Relatórios', 'bar_chart')]),
    ]
    with st.sidebar:
        st.markdown('''<div class="brand"><div class="brand-mark" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
        <path d="M12 5v15M12 5C9 3 5 3 2 4v14c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1Z"/></svg>
        </div><div><div class="brand-name">Biblioteca</div><div class="brand-note">Gestão do acervo</div></div></div>''', unsafe_allow_html=True)
        for titulo, itens in grupos:
            st.markdown(f'<div class="nav-group">{titulo}</div>', unsafe_allow_html=True)
            for pagina, rotulo, icone in itens:
                st.button(rotulo, key=f'nav_{pagina}', icon=f':material/{icone}:', width='stretch',
                          type='primary' if st.session_state['pagina_atual'] == pagina else 'secondary',
                          on_click=navegar, args=(pagina,))
        st.markdown('<div class="sidebar-footer"><strong>Seu acervo, organizado.</strong></div>', unsafe_allow_html=True)
        st.button('Atualizar dados', icon=':material/refresh:', width='stretch', key='atualizar_dados')
    return st.session_state['pagina_atual']
