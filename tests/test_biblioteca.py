"""Testes reais com SQLite temporário; nunca usam o banco do estudante."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

from biblioteca import Biblioteca, ErroBiblioteca
from database import BancoDados


class BibliotecaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = BancoDados(Path(self.temp.name) / 'teste.db')
        self.s = Biblioteca(self.db)
        self.l = self.s.cadastrar_livro('Ação [Python]', 'José Silva', 2020, 1)
        self.u = self.s.cadastrar_usuario('Ana', 'RA-1', 'ana@example.com')

    def test_ciclo_preserva_total_e_registra_datas(self):
        e = self.s.emprestar(self.l, self.u)
        self.assertEqual(self.s.indicadores(), dict(titulos=1, disponiveis=0, emprestados=1, total=1, usuarios=1))
        self.assertIsNotNone(self.s.listar_emprestimos()[0]['data_emprestimo'])
        self.s.devolver(e)
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)
        self.assertEqual(self.s.indicadores()['total'], 1)
        self.assertEqual(self.s.listar_emprestimos('Devolvido')[0]['status'], 'Devolvido')
        self.assertIsNotNone(self.s.listar_emprestimos()[0]['data_devolucao'])

    def test_ultima_copia_nao_pode_ser_emprestada_duas_vezes(self):
        self.s.emprestar(self.l, self.u)
        with self.assertRaises(ErroBiblioteca):
            self.s.emprestar(self.l, self.u)
        self.assertEqual(len(self.s.listar_emprestimos()), 1)
        self.assertEqual(self.s.indicadores()['disponiveis'], 0)

    def test_devolucao_repetida_nao_aumenta_estoque(self):
        e = self.s.emprestar(self.l, self.u)
        self.s.devolver(e)
        with self.assertRaises(ErroBiblioteca):
            self.s.devolver(e)
        self.assertEqual(self.s.indicadores()['total'], 1)

    def test_ids_inexistentes_nao_alteram_dados(self):
        for livro, usuario in [(999, self.u), (self.l, 999)]:
            with self.subTest(livro=livro, usuario=usuario):
                with self.assertRaises(ErroBiblioteca):
                    self.s.emprestar(livro, usuario)
        with self.assertRaises(ErroBiblioteca):
            self.s.devolver(999)
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)
        self.assertEqual(self.s.listar_emprestimos(), [])

    def test_busca_literal_acentos_autor_e_ano(self):
        for termo in ['[', 'acao', 'JOSÉ', '2020', ' python ']:
            with self.subTest(termo=termo):
                self.assertEqual(len(self.s.listar_livros(termo)), 1)
        for termo in ['%', '.', 'inexistente']:
            self.assertEqual(self.s.listar_livros(termo), [])

    def test_rejeita_campos_vazios_e_ano_invalido(self):
        for titulo, autor, ano, copias in [(' ', 'Autor', 2000, 1), ('Livro', ' ', 2000, 1),
                                          ('Livro', 'Autor', date.today().year+1, 1),
                                          ('Livro', 'Autor', 2000, -1), ('Livro', 'Autor', 2000, 1.5)]:
            with self.subTest(titulo=titulo, ano=ano, copias=copias):
                with self.assertRaises(ErroBiblioteca):
                    self.s.cadastrar_livro(titulo, autor, ano, copias)
        for dados in [(' ', '2', 'email'), ('Ana', ' ', 'email'), ('Ana', '2', ' ')]:
            with self.assertRaises(ErroBiblioteca):
                self.s.cadastrar_usuario(*dados)
        self.assertEqual(self.s.indicadores()['titulos'], 1)

    def test_identificacao_duplicada_apos_remover_espacos(self):
        with self.assertRaises(ErroBiblioteca):
            self.s.cadastrar_usuario('Outra pessoa', ' RA-1 ', 'telefone')
        self.assertEqual(len(self.s.listar_usuarios()), 1)

    def test_titulos_iguais_mantem_ids_distintos(self):
        outro = self.s.cadastrar_livro('Ação [Python]', 'Outro autor', 2021, 1)
        self.assertNotEqual(outro, self.l)
        self.assertEqual(len(self.s.listar_livros()), 2)

    def test_relatorios_separam_disponiveis_ativos_historico(self):
        self.s.cadastrar_livro('Sem estoque', 'Autor', 2000, 0)
        self.assertEqual(len(self.s.listar_livros(somente_disponiveis=True)), 1)
        e = self.s.emprestar(self.l, self.u)
        self.assertEqual(self.s.listar_livros(somente_disponiveis=True), [])
        self.assertEqual(len(self.s.listar_emprestimos('Emprestado')), 1)
        self.s.devolver(e)
        self.assertEqual(self.s.listar_emprestimos('Emprestado'), [])
        self.assertEqual(len(self.s.listar_emprestimos()), 1)

    def test_editar_preserva_id_e_vinculo(self):
        self.s.emprestar(self.l, self.u)
        self.s.editar_livro(self.l, ' Novo título ', 'Autora', 2022)
        self.s.editar_usuario(self.u, ' Ana Maria ', 'RA-2', '11999999999')
        e = self.s.listar_emprestimos()[0]
        self.assertEqual((e['titulo'], e['nome'], e['identificacao']), ('Novo título', 'Ana Maria', 'RA-2'))
        self.assertEqual(self.s.indicadores()['disponiveis'], 0)

    def test_edicao_inexistente_e_identificacao_duplicada(self):
        outro = self.s.cadastrar_usuario('Bia', 'RA-2', 'contato')
        with self.assertRaises(ErroBiblioteca):
            self.s.editar_usuario(outro, 'Bia', 'RA-1', 'contato')
        with self.assertRaises(ErroBiblioteca):
            self.s.editar_livro(999, 'Título', 'Autor', 2000)
        with self.assertRaises(ErroBiblioteca):
            self.s.editar_usuario(999, 'Nome', 'ID', 'contato')
        self.assertEqual(self.s.listar_usuarios('RA-2')[0]['nome'], 'Bia')

    def test_adicionar_exemplares_mantem_emprestimos(self):
        self.s.emprestar(self.l, self.u)
        self.s.adicionar_copias(self.l, 3)
        self.assertEqual(self.s.indicadores()['total'], 4)
        self.assertEqual(self.s.indicadores()['disponiveis'], 3)
        for qtd in [0, -1]:
            with self.assertRaises(ErroBiblioteca):
                self.s.adicionar_copias(self.l, qtd)
        with self.assertRaises(ErroBiblioteca):
            self.s.adicionar_copias(999, 1)

    def test_banco_rejeita_estoque_negativo_e_referencia_orfa(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.conexao() as c:
                c.execute('UPDATE livros SET copias_disponiveis=-1 WHERE id=?', (self.l,))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.conexao() as c:
                c.execute("INSERT INTO emprestimos(id_livro,id_usuario,status) VALUES(999,999,'Emprestado')")
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)

    def test_falha_de_insercao_reverte_reducao_de_estoque(self):
        with self.db.conexao() as c:
            c.execute("CREATE TRIGGER falha BEFORE INSERT ON emprestimos BEGIN SELECT RAISE(ABORT, 'falha simulada'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.emprestar(self.l, self.u)
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)
        self.assertEqual(self.s.listar_emprestimos(), [])

    def test_concorrencia_ultima_copia(self):
        barreira = Barrier(2)
        def tentar(_):
            barreira.wait(timeout=5)
            try:
                self.s.emprestar(self.l, self.u)
                return True
            except ErroBiblioteca:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(tentar, range(2))), [False, True])
        self.assertEqual(self.s.indicadores()['disponiveis'], 0)
        self.assertEqual(len(self.s.listar_emprestimos()), 1)

    def test_concorrencia_devolucao(self):
        e = self.s.emprestar(self.l, self.u)
        barreira = Barrier(2)
        def tentar(_):
            barreira.wait(timeout=5)
            try:
                self.s.devolver(e)
                return True
            except ErroBiblioteca:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(tentar, range(2))), [False, True])
        self.assertEqual(self.s.indicadores()['disponiveis'], 1)


LEGADO = '''
CREATE TABLE livros(id INTEGER PRIMARY KEY AUTOINCREMENT,titulo TEXT NOT NULL,autor TEXT NOT NULL,ano INTEGER NOT NULL,copias_disponiveis INTEGER NOT NULL);
CREATE TABLE usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,identificacao TEXT UNIQUE NOT NULL,contato TEXT NOT NULL);
CREATE TABLE emprestimos(id INTEGER PRIMARY KEY AUTOINCREMENT,id_livro INTEGER NOT NULL,id_usuario INTEGER NOT NULL,status TEXT DEFAULT 'Emprestado',FOREIGN KEY(id_livro) REFERENCES livros(id),FOREIGN KEY(id_usuario) REFERENCES usuarios(id));
INSERT INTO livros VALUES(7,'Legado','Autor',2000,2);
INSERT INTO usuarios VALUES(9,'Pessoa','ID-9','contato');
INSERT INTO emprestimos VALUES(11,7,9,'Emprestado');
'''


class MigracaoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'legado.db'
        with closing(sqlite3.connect(self.path)) as c, c:
            c.executescript(LEGADO)

    def test_migracao_preserva_ids_dados_e_datas_desconhecidas(self):
        s = Biblioteca(BancoDados(self.path))
        self.assertEqual(s.listar_livros()[0]['id'], 7)
        self.assertEqual(s.listar_usuarios()[0]['id'], 9)
        e = s.listar_emprestimos()[0]
        self.assertEqual(e['id'], 11)
        self.assertIsNone(e['data_emprestimo'])
        self.assertEqual(s.indicadores()['total'], 3)
        s.devolver(11)
        self.assertEqual(s.indicadores()['disponiveis'], 3)
        Biblioteca(BancoDados(self.path))
        self.assertEqual(len(s.listar_emprestimos()), 1)

    def test_legado_invalido_faz_rollback_integral(self):
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('UPDATE livros SET copias_disponiveis=-1')
        with self.assertRaises(sqlite3.IntegrityError):
            BancoDados(self.path)
        with closing(sqlite3.connect(self.path)) as c, c:
            self.assertEqual(c.execute('SELECT copias_disponiveis FROM livros').fetchone()[0], -1)
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM emprestimos').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
