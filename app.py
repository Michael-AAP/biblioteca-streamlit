"""Interface do sistema. Execute: python -m streamlit run app.py"""
from datetime import date, datetime
import logging
import os
import sqlite3

import pandas as pd
import streamlit as st

from biblioteca import Biblioteca, ErroBiblioteca
from database import BancoDados
from visual import aplicar_visual, navegacao, navegar, indicador


LIVROS = {'id': 'ID', 'titulo': 'Título', 'autor': 'Autor', 'ano': 'Ano',
          'copias_total': 'Total de cópias', 'copias_disponiveis': 'Disponíveis', 'copias_emprestadas': 'Emprestadas'}
USUARIOS = {'id': 'ID', 'nome': 'Nome', 'identificacao': 'Identificação', 'contato': 'Contato',
            'emprestimos_ativos': 'Empréstimos ativos'}
EMPRESTIMOS = {'id': 'Empréstimo', 'id_livro': 'ID do livro', 'titulo': 'Título', 'autor': 'Autor',
               'nome': 'Usuário', 'identificacao': 'Identificação', 'status': 'Situação',
               'data_emprestimo': 'Data do empréstimo (UTC)', 'data_devolucao': 'Data da devolução (UTC)'}


def tabela(registros, colunas, chave):
    """Exibe e exporta exatamente os registros consultados."""
    if not registros:
        st.info('Nenhum registro encontrado para esta consulta.')
        return
    df = pd.DataFrame(registros).reindex(columns=list(colunas))
    for campo in ('data_emprestimo', 'data_devolucao'):
        if campo in df:
            df[campo] = df[campo].map(
                lambda valor: datetime.fromisoformat(valor).strftime('%d/%m/%Y %H:%M:%S')
                if valor else 'Não registrada')
    df = df.rename(columns=colunas)
    st.dataframe(df, hide_index=True, width='stretch')
    st.caption(f'{len(df)} registro(s).')
    # Evita que texto cadastrado seja interpretado como fórmula ao abrir o CSV.
    seguro = df.map(lambda v: "'" + v if isinstance(v, str) and
                    (v.lstrip().startswith(('=', '+', '-', '@')) or v.startswith(('\t', '\r', '\n'))) else v)
    st.download_button('Exportar CSV', seguro.to_csv(index=False, sep=';').encode('utf-8-sig'),
                       icon=':material/download:',
                       file_name=f'{chave}.csv', mime='text/csv', key=f'csv_{chave}')


def concluir(mensagem):
    st.session_state['mensagem_sucesso'] = mensagem
    st.session_state['revisao'] = st.session_state.get('revisao', 0) + 1
    st.rerun()


def executar(operacao, mensagem):
    try:
        operacao()
    except ErroBiblioteca as erro:
        st.error(str(erro))
    else:
        concluir(mensagem)


def rotulo_livro(livro):
    return f"#{livro['id']} · {livro['titulo']} — {livro['autor']} ({livro['ano']})"


def consulta(s):
    titulo, acao = st.columns([4, 1], vertical_alignment='center')
    with titulo:
        st.title('Acervo da biblioteca')
        st.caption('Encontre uma leitura e acompanhe a disponibilidade dos exemplares.')
    with acao:
        st.button('Cadastrar livro', icon=':material/add:', type='primary', width='stretch',
                  key='atalho_cadastro', on_click=navegar, args=('Cadastro de Livros',))
    indicadores = s.indicadores()
    for coluna, campo, rotulo in zip(st.columns(3), ['titulos', 'disponiveis', 'emprestados'],
                                     ['Títulos no acervo', 'Disponíveis', 'Emprestados']):
        with coluna:
            indicador(campo, rotulo, indicadores[campo])
    with st.container(key='painel_consulta'):
        st.subheader('Catálogo de livros')
        pesquisa, filtro = st.columns([3, 1])
        with pesquisa:
            busca = st.text_input('Buscar no acervo', placeholder='Título, autor ou ano de publicação',
                                  icon=':material/search:')
        with filtro:
            disponiveis = st.checkbox('Somente disponíveis', key='filtro_disponiveis')
        tabela(s.listar_livros(busca, disponiveis), LIVROS, 'consulta_acervo')


def cadastro_livros(s):
    st.title('Gerenciar livros')
    st.caption('Cadastre novas leituras, revise informações e mantenha o estoque atualizado.')
    novo, editar, repor = st.tabs(['Novo livro', 'Editar cadastro', 'Adicionar exemplares'])
    revisao = st.session_state.get('revisao', 0)
    with novo:
        with st.form(f'novo_livro_{revisao}'):
            titulo = st.text_input('Título', max_chars=200)
            autor = st.text_input('Autor', max_chars=200)
            a, b = st.columns(2)
            ano = a.number_input('Ano de publicação', min_value=1, max_value=date.today().year, value=date.today().year)
            copias = b.number_input('Cópias disponíveis', min_value=0, max_value=1_000_000, value=1)
            if st.form_submit_button('Cadastrar livro', key='salvar_livro', type='primary'):
                executar(lambda: s.cadastrar_livro(titulo, autor, ano, copias), 'Livro cadastrado com sucesso.')
    livros = {r['id']: r for r in s.listar_livros()}
    with editar:
        if not livros:
            st.info('Cadastre um livro para editar seus dados.')
        else:
            livro_id = st.selectbox('Livro a editar', list(livros), format_func=lambda i: rotulo_livro(livros[i]), key='editar_livro_id')
            livro = livros[livro_id]
            with st.form(f'editar_livro_{livro_id}_{revisao}'):
                titulo = st.text_input('Título', value=livro['titulo'], max_chars=200)
                autor = st.text_input('Autor', value=livro['autor'], max_chars=200)
                ano = st.number_input('Ano de publicação', min_value=1, max_value=max(date.today().year, livro['ano']), value=livro['ano'])
                st.caption('A edição dos dados mantém o estoque e os empréstimos vinculados ao livro.')
                if st.form_submit_button('Salvar alterações', key='editar_livro_salvar'):
                    executar(lambda: s.editar_livro(livro_id, titulo, autor, ano), 'Cadastro do livro atualizado.')
    with repor:
        if not livros:
            st.info('Cadastre um livro antes de adicionar exemplares.')
        else:
            with st.form(f'repor_{revisao}'):
                livro_id = st.selectbox('Livro que recebeu exemplares', list(livros), format_func=lambda i: rotulo_livro(livros[i]), key='repor_livro')
                qtd = st.number_input('Quantidade recebida', min_value=1, max_value=1_000_000, value=1)
                if st.form_submit_button('Adicionar ao acervo', key='adicionar_copias'):
                    executar(lambda: s.adicionar_copias(livro_id, qtd), 'Exemplares adicionados ao acervo.')


def cadastro_usuarios(s):
    st.title('Usuários da biblioteca')
    st.caption('Organize os cadastros e acompanhe quem utiliza o acervo.')
    novo, editar, lista = st.tabs(['Novo usuário', 'Editar cadastro', 'Usuários cadastrados'])
    revisao = st.session_state.get('revisao', 0)
    with novo:
        with st.form(f'novo_usuario_{revisao}'):
            nome = st.text_input('Nome completo', max_chars=200)
            identificacao = st.text_input('Identificação (matrícula, RA ou outro código)', max_chars=80)
            contato = st.text_input('Contato (telefone ou e-mail)', max_chars=200)
            if st.form_submit_button('Cadastrar usuário', key='salvar_usuario', type='primary'):
                executar(lambda: s.cadastrar_usuario(nome, identificacao, contato), 'Usuário cadastrado com sucesso.')
    usuarios = {r['id']: r for r in s.listar_usuarios()}
    with editar:
        if not usuarios:
            st.info('Cadastre um usuário para editar seus dados.')
        else:
            usuario_id = st.selectbox('Usuário a editar', list(usuarios), key='editar_usuario_id',
                                     format_func=lambda i: f"#{i} · {usuarios[i]['nome']} ({usuarios[i]['identificacao']})")
            usuario = usuarios[usuario_id]
            with st.form(f'editar_usuario_{usuario_id}_{revisao}'):
                nome = st.text_input('Nome completo', value=usuario['nome'], max_chars=200)
                identificacao = st.text_input('Identificação', value=usuario['identificacao'], max_chars=80)
                contato = st.text_input('Contato', value=usuario['contato'], max_chars=200)
                if st.form_submit_button('Salvar alterações', key='editar_usuario_salvar'):
                    executar(lambda: s.editar_usuario(usuario_id, nome, identificacao, contato), 'Cadastro do usuário atualizado.')
    with lista:
        busca = st.text_input('Buscar usuário por nome, identificação ou contato')
        tabela(s.listar_usuarios(busca), USUARIOS, 'usuarios_cadastrados')


def emprestimo(s):
    st.title('Novo empréstimo')
    st.caption('Escolha um exemplar disponível e o usuário que vai recebê-lo.')
    livros = {r['id']: r for r in s.listar_livros(somente_disponiveis=True)}
    usuarios = {r['id']: r for r in s.listar_usuarios()}
    if not livros:
        st.info('Não há exemplares disponíveis. Cadastre livros, adicione exemplares ou registre uma devolução.')
        return
    if not usuarios:
        st.info('Cadastre pelo menos um usuário antes de realizar empréstimos.')
        return
    with st.form('emprestimo'):
        livro_id = st.selectbox('Livro disponível', list(livros), key='emprestimo_livro',
                                format_func=lambda i: f"{rotulo_livro(livros[i])} · {livros[i]['copias_disponiveis']} disponível(is)")
        usuario_id = st.selectbox('Usuário', list(usuarios), key='emprestimo_usuario',
                                  format_func=lambda i: f"#{i} · {usuarios[i]['nome']} ({usuarios[i]['identificacao']})")
        st.caption('Cada confirmação registra o empréstimo de um exemplar.')
        if st.form_submit_button('Confirmar empréstimo', key='confirmar_emprestimo', type='primary'):
            executar(lambda: s.emprestar(livro_id, usuario_id), 'Empréstimo registrado. Disponibilidade atualizada.')


def devolucao(s):
    st.title('Registrar devolução')
    st.caption('Conclua um empréstimo e disponibilize o exemplar para a próxima leitura.')
    registros = {r['id']: r for r in s.listar_emprestimos('Emprestado')}
    if not registros:
        st.info('Não há empréstimos pendentes de devolução.')
        return
    with st.form('devolucao'):
        emprestimo_id = st.selectbox('Empréstimo a devolver', list(registros), key='devolucao_id',
            format_func=lambda i: f"Empréstimo #{i} · Livro #{registros[i]['id_livro']}: {registros[i]['titulo']} · {registros[i]['nome']} ({registros[i]['identificacao']})")
        if st.form_submit_button('Confirmar devolução', key='confirmar_devolucao', type='primary'):
            executar(lambda: s.devolver(emprestimo_id), 'Devolução concluída. O exemplar está disponível novamente.')
    tabela(list(registros.values()), EMPRESTIMOS, 'pendentes_devolucao')


def relatorios(s):
    st.title('Visão geral da biblioteca')
    st.caption('Acompanhe o acervo, a circulação e o histórico em um só lugar.')
    indicadores = s.indicadores()
    campos = [('titulos', 'Títulos'), ('total', 'Exemplares'),
              ('disponiveis', 'Disponíveis'), ('emprestados', 'Emprestados'), ('usuarios', 'Usuários')]
    for coluna, (campo, rotulo) in zip(st.columns(5), campos):
        with coluna:
            indicador(campo, rotulo, indicadores[campo])
    st.caption('Total de exemplares = disponíveis + empréstimos ativos. Cada empréstimo representa um exemplar.')
    acervo, disponiveis, ativos, usuarios, historico = st.tabs([
        'Acervo completo', 'Livros disponíveis', 'Empréstimos ativos', 'Usuários', 'Histórico'])
    with acervo:
        tabela(s.listar_livros(), LIVROS, 'acervo_completo')
    with disponiveis:
        tabela(s.listar_livros(somente_disponiveis=True), LIVROS, 'livros_disponiveis')
    with ativos:
        tabela(s.listar_emprestimos('Emprestado'), EMPRESTIMOS, 'emprestimos_ativos')
    with usuarios:
        tabela(s.listar_usuarios(), USUARIOS, 'relatorio_usuarios')
    with historico:
        status = st.selectbox('Situação', ['Todos', 'Emprestado', 'Devolvido'])
        st.caption('Datas em UTC. Registros anteriores à atualização podem não possuir datas registradas.')
        tabela(s.listar_emprestimos(None if status == 'Todos' else status), EMPRESTIMOS, 'historico_emprestimos')


def main():
    st.set_page_config(page_title='Biblioteca | Gestão do acervo', page_icon=':material/auto_stories:',
                       layout='wide', initial_sidebar_state='auto')
    aplicar_visual()
    paginas = {'Consulta de Livros': consulta, 'Cadastro de Livros': cadastro_livros,
               'Cadastro de Usuários': cadastro_usuarios, 'Empréstimo de Livros': emprestimo,
               'Devolução de Livros': devolucao, 'Relatórios': relatorios}
    menu = navegacao()
    st.markdown('<div class="page-kicker">BIBLIOTECA &nbsp; / &nbsp; GESTÃO DO ACERVO</div>', unsafe_allow_html=True)
    mensagem = st.session_state.pop('mensagem_sucesso', None)
    if mensagem:
        st.success(mensagem)
    try:
        sistema = Biblioteca(BancoDados(os.environ.get('BIBLIOTECA_DB')))
        paginas[menu](sistema)
    except ErroBiblioteca as erro:
        st.error(str(erro))
    except (sqlite3.Error, OSError, ValueError):
        logging.exception('Falha ao acessar os dados da biblioteca')
        st.error('Não foi possível concluir a operação. Verifique se a pasta permite gravação e se o banco é compatível. Os detalhes estão no terminal.')
        st.info('Se o banco estiver em uso por outro processo, aguarde e clique em Atualizar dados.')


if __name__ == '__main__':
    main()
