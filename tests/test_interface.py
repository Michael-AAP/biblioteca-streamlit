"""Fluxos Streamlit com banco descartável e sem servidor externo."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from biblioteca import Biblioteca
from database import BancoDados


APP = Path(__file__).resolve().parents[1] / 'app.py'


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ui.db'
        env = patch.dict(os.environ, {'BIBLIOTECA_DB': str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        self.s = Biblioteca(BancoDados(self.path))

    def app(self, menu=None):
        a = AppTest.from_file(str(APP), default_timeout=30).run()
        if menu:
            a.sidebar.button(key=f'nav_{menu}').click().run()
        self.assertEqual(len(a.exception), 0)
        return a

    def test_telas_vazias_e_indicadores_zero(self):
        a = self.app()
        for menu in ['Consulta de Livros','Cadastro de Livros','Cadastro de Usuários',
                     'Empréstimo de Livros','Devolução de Livros','Relatórios']:
            a.sidebar.button(key=f'nav_{menu}').click().run()
            self.assertEqual(len(a.exception), 0, menu)
        self.assertEqual([m.value for m in a.metric], ['0', '0', '0', '0', '0'])

    def test_cadastro_por_formulario(self):
        a = self.app('Cadastro de Livros')
        a.text_input[0].input('Livro cadastrado')
        a.text_input[1].input('Autora')
        a.button(key='salvar_livro').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.listar_livros()[0]['titulo'], 'Livro cadastrado')
        self.assertTrue(a.success)
        a.sidebar.button(key='nav_Cadastro de Usuários').click().run()
        a.text_input[0].input('Estudante')
        a.text_input[1].input('RA-TESTE')
        a.text_input[2].input('teste@example.com')
        a.button(key='salvar_usuario').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.listar_usuarios()[0]['identificacao'], 'RA-TESTE')

    def test_busca_colchete_e_titulos_iguais(self):
        self.s.cadastrar_livro('Livro [teste]', 'Autor A', 2000, 1)
        self.s.cadastrar_livro('Livro [teste]', 'Autor B', 2001, 1)
        self.s.cadastrar_usuario('Ana', '1', 'contato')
        a = self.app('Consulta de Livros')
        a.text_input[0].input('[').run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(len(a.dataframe[0].value), 2)
        a.sidebar.button(key='nav_Empréstimo de Livros').click().run()
        self.assertEqual(len(a.selectbox(key='emprestimo_livro').options), 2)
        self.assertNotEqual(*a.selectbox(key='emprestimo_livro').options)

    def test_ciclo_interface_atualiza_listagens(self):
        self.s.cadastrar_livro('Livro', 'Autor', 2000, 1)
        self.s.cadastrar_usuario('Ana', '1', 'contato')
        a = self.app('Empréstimo de Livros')
        a.button(key='confirmar_emprestimo').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.indicadores()['emprestados'], 1)
        self.assertTrue(a.success)
        self.assertEqual(len(a.selectbox), 0)  # Estoque esgotado: nenhuma seleção de empréstimo.
        a.sidebar.button(key='nav_Devolução de Livros').click().run()
        a.button(key='confirmar_devolucao').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)
        self.assertEqual(self.s.indicadores()['emprestados'], 0)
        self.assertTrue(a.success)

    def test_relatorio_inclui_usuario_sem_emprestimo(self):
        self.s.cadastrar_usuario('Sem empréstimo', 'RA-9', 'contato')
        a = self.app('Relatórios')
        tabelas = [d.value for d in a.dataframe]
        self.assertTrue(any('Nome' in t.columns and 'Sem empréstimo' in t['Nome'].values for t in tabelas))

    def test_edicao_e_reposicao_pela_interface(self):
        self.s.cadastrar_livro('Título antigo', 'Autor', 2000, 1)
        a = self.app('Cadastro de Livros')
        a.text_input[2].input('Título corrigido')
        a.button(key='editar_livro_salvar').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.listar_livros()[0]['titulo'], 'Título corrigido')
        a.button(key='adicionar_copias').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.indicadores()['total'], 2)

    def test_identificacao_duplicada_exibe_erro_sem_apagar_formulario(self):
        self.s.cadastrar_usuario('Ana', 'RA-1', 'contato')
        a = self.app('Cadastro de Usuários')
        a.text_input[0].input('Outra pessoa')
        a.text_input[1].input('RA-1')
        a.text_input[2].input('telefone')
        a.button(key='salvar_usuario').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertTrue(a.error)
        self.assertEqual(a.text_input[0].value, 'Outra pessoa')
        self.assertEqual(len(self.s.listar_usuarios()), 1)

    def test_devolucao_distingue_homonimos_e_emprestimos_repetidos(self):
        livro = self.s.cadastrar_livro('Mesmo título', 'Autor', 2000, 3)
        u1 = self.s.cadastrar_usuario('Ana', 'RA-1', 'contato')
        u2 = self.s.cadastrar_usuario('Ana', 'RA-2', 'contato')
        self.s.emprestar(livro, u1)
        self.s.emprestar(livro, u1)
        self.s.emprestar(livro, u2)
        a = self.app('Devolução de Livros')
        self.assertEqual(len(set(a.selectbox(key='devolucao_id').options)), 3)
        a.button(key='confirmar_devolucao').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.indicadores()['emprestados'], 2)

    def test_editar_usuario_pela_interface(self):
        self.s.cadastrar_usuario('Nome antigo', 'RA-1', 'contato')
        a = self.app('Cadastro de Usuários')
        a.text_input[3].input('Nome atualizado')
        a.button(key='editar_usuario_salvar').click().run()
        self.assertEqual(len(a.exception), 0)
        self.assertEqual(self.s.listar_usuarios()[0]['nome'], 'Nome atualizado')


if __name__ == '__main__':
    unittest.main()
