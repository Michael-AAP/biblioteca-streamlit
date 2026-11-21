"""Persistência SQLite, conexões curtas e migração do projeto original."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


SCHEMA = (
    """CREATE TABLE livros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL CHECK(length(trim(titulo)) > 0),
        autor TEXT NOT NULL CHECK(length(trim(autor)) > 0),
        ano INTEGER NOT NULL CHECK(typeof(ano)='integer' AND ano BETWEEN 1 AND 9999),
        copias_disponiveis INTEGER NOT NULL
            CHECK(typeof(copias_disponiveis)='integer' AND copias_disponiveis >= 0)
    )""",
    """CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL CHECK(length(trim(nome)) > 0),
        identificacao TEXT UNIQUE NOT NULL CHECK(length(trim(identificacao)) > 0),
        contato TEXT NOT NULL CHECK(length(trim(contato)) > 0)
    )""",
    """CREATE TABLE emprestimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_livro INTEGER NOT NULL REFERENCES livros(id) ON DELETE RESTRICT,
        id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
        status TEXT NOT NULL DEFAULT 'Emprestado' CHECK(status IN ('Emprestado','Devolvido')),
        data_emprestimo TEXT,
        data_devolucao TEXT,
        CHECK(status='Devolvido' OR data_devolucao IS NULL)
    )""",
    'CREATE INDEX idx_emprestimos_livro ON emprestimos(id_livro)',
    'CREATE INDEX idx_emprestimos_usuario ON emprestimos(id_usuario)',
    'CREATE INDEX idx_emprestimos_status ON emprestimos(status)',
)


class BancoDados:
    """Abre uma conexão por operação, sem compartilhar cursores entre sessões."""

    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else Path(__file__).with_name('biblioteca.db')
        self.caminho = self.caminho.resolve()
        self.inicializar()

    @contextmanager
    def conexao(self):
        conexao = sqlite3.connect(self.caminho, timeout=10)
        conexao.row_factory = sqlite3.Row
        conexao.execute('PRAGMA foreign_keys = ON')
        try:
            with conexao:  # Confirma no sucesso e desfaz em qualquer exceção.
                yield conexao
        finally:
            conexao.close()

    def inicializar(self):
        with self.conexao() as c:
            versao = c.execute('PRAGMA user_version').fetchone()[0]
            if versao == 1:
                return
            if versao != 0:
                raise ValueError('Versão do banco incompatível com este aplicativo.')
            # Serializa a migração; outra sessão pode ter terminado enquanto aguardávamos.
            c.execute('BEGIN IMMEDIATE')
            if c.execute('PRAGMA user_version').fetchone()[0] == 1:
                return
            tabelas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            antigas = {}
            sequencias = []
            if tabelas:
                if tabelas != {'livros', 'usuarios', 'emprestimos'}:
                    raise ValueError('Estrutura do banco não reconhecida. Migração cancelada.')
                colunas = {
                    'livros': ['id', 'titulo', 'autor', 'ano', 'copias_disponiveis'],
                    'usuarios': ['id', 'nome', 'identificacao', 'contato'],
                    'emprestimos': ['id', 'id_livro', 'id_usuario', 'status'],
                }
                for tabela, esperadas in colunas.items():
                    # Os nomes interpolados são constantes internas, nunca entradas do usuário.
                    existentes = [r['name'] for r in c.execute(f'PRAGMA table_info({tabela})')]
                    if existentes != esperadas:
                        raise ValueError('Estrutura legada diferente da esperada. Migração cancelada.')
                    antigas[tabela] = [tuple(r) for r in c.execute(f'SELECT * FROM {tabela}')]
                if c.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
                    sequencias = list(c.execute('SELECT name,seq FROM sqlite_sequence'))
                for tabela in ['emprestimos', 'livros', 'usuarios']:
                    c.execute(f'DROP TABLE {tabela}')
            # Não usar executescript: manter DDL e cópia de dados na mesma transação.
            for comando in SCHEMA:
                c.execute(comando)
            if antigas:
                c.executemany('INSERT INTO livros VALUES(?,?,?,?,?)', antigas['livros'])
                c.executemany('INSERT INTO usuarios VALUES(?,?,?,?)', antigas['usuarios'])
                c.executemany('INSERT INTO emprestimos(id,id_livro,id_usuario,status) VALUES(?,?,?,?)', antigas['emprestimos'])
                for nome, seq in sequencias:
                    c.execute('UPDATE sqlite_sequence SET seq=max(seq,?) WHERE name=?', (seq, nome))
                    if not c.execute('SELECT 1 FROM sqlite_sequence WHERE name=?', (nome,)).fetchone():
                        c.execute('INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)', (nome, seq))
            if c.execute('PRAGMA foreign_key_check').fetchone():
                raise sqlite3.IntegrityError('Existem empréstimos sem livro ou usuário correspondente.')
            c.execute('PRAGMA user_version = 1')
