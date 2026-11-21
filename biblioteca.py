"""Regras de negócio independentes da interface Streamlit."""
from datetime import date, datetime, timezone
import sqlite3
import unicodedata

from database import BancoDados


class ErroBiblioteca(ValueError):
    """Situação prevista que pode ser explicada diretamente ao usuário."""


def _texto(valor, campo, limite=200):
    if not isinstance(valor, str) or not valor.strip():
        raise ErroBiblioteca(f'Preencha o campo {campo}.')
    valor = valor.strip()
    if len(valor) > limite:
        raise ErroBiblioteca(f'{campo}: use no máximo {limite} caracteres.')
    return valor


def _inteiro(valor, campo, minimo=0, maximo=1_000_000):
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ErroBiblioteca(f'{campo} deve ser um número inteiro entre {minimo} e {maximo}.')
    return valor


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto))
                   if not unicodedata.combining(c)).casefold().strip()


def _filtrar(registros, busca, campos):
    termo = _normalizar(busca)
    return [r for r in registros if any(termo in _normalizar(r[c]) for c in campos)]


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Biblioteca:
    """Encapsula cadastros, circulação e consultas usando composição com BancoDados."""

    def __init__(self, banco: BancoDados):
        self.banco = banco

    def cadastrar_livro(self, titulo, autor, ano, copias):
        titulo, autor = _texto(titulo, 'Título'), _texto(autor, 'Autor')
        ano = _inteiro(ano, 'Ano', 1, date.today().year)
        copias = _inteiro(copias, 'Cópias')
        with self.banco.conexao() as c:
            return c.execute('INSERT INTO livros(titulo,autor,ano,copias_disponiveis) VALUES(?,?,?,?)',
                             (titulo, autor, ano, copias)).lastrowid

    def editar_livro(self, livro_id, titulo, autor, ano):
        titulo, autor = _texto(titulo, 'Título'), _texto(autor, 'Autor')
        ano = _inteiro(ano, 'Ano', 1, date.today().year)
        with self.banco.conexao() as c:
            if c.execute('UPDATE livros SET titulo=?,autor=?,ano=? WHERE id=?',
                         (titulo, autor, ano, livro_id)).rowcount != 1:
                raise ErroBiblioteca('Livro não encontrado. Atualize a tela.')

    def adicionar_copias(self, livro_id, quantidade):
        quantidade = _inteiro(quantidade, 'Quantidade', 1)
        with self.banco.conexao() as c:
            if c.execute('UPDATE livros SET copias_disponiveis=copias_disponiveis+? WHERE id=?',
                         (quantidade, livro_id)).rowcount != 1:
                raise ErroBiblioteca('Livro não encontrado. Atualize a tela.')

    def cadastrar_usuario(self, nome, identificacao, contato):
        dados = (_texto(nome, 'Nome'), _texto(identificacao, 'Identificação', 80), _texto(contato, 'Contato'))
        try:
            with self.banco.conexao() as c:
                return c.execute('INSERT INTO usuarios(nome,identificacao,contato) VALUES(?,?,?)', dados).lastrowid
        except sqlite3.IntegrityError as erro:
            if 'usuarios.identificacao' in str(erro):
                raise ErroBiblioteca('Esta identificação já está cadastrada.') from erro
            raise

    def editar_usuario(self, usuario_id, nome, identificacao, contato):
        dados = (_texto(nome, 'Nome'), _texto(identificacao, 'Identificação', 80), _texto(contato, 'Contato'), usuario_id)
        try:
            with self.banco.conexao() as c:
                if c.execute('UPDATE usuarios SET nome=?,identificacao=?,contato=? WHERE id=?', dados).rowcount != 1:
                    raise ErroBiblioteca('Usuário não encontrado. Atualize a tela.')
        except sqlite3.IntegrityError as erro:
            if 'usuarios.identificacao' in str(erro):
                raise ErroBiblioteca('Esta identificação já está cadastrada.') from erro
            raise

    def emprestar(self, livro_id, usuario_id):
        with self.banco.conexao() as c:
            # A reserva de escrita acontece antes das consultas: duas sessões não consomem a última cópia.
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM usuarios WHERE id=?', (usuario_id,)).fetchone():
                raise ErroBiblioteca('Usuário não encontrado. Atualize a tela.')
            if not c.execute('SELECT 1 FROM livros WHERE id=?', (livro_id,)).fetchone():
                raise ErroBiblioteca('Livro não encontrado. Atualize a tela.')
            alterados = c.execute('UPDATE livros SET copias_disponiveis=copias_disponiveis-1 WHERE id=? AND copias_disponiveis>0',
                                 (livro_id,)).rowcount
            if alterados != 1:
                raise ErroBiblioteca('Este livro não possui cópias disponíveis. Atualize a tela.')
            return c.execute("INSERT INTO emprestimos(id_livro,id_usuario,status,data_emprestimo) VALUES(?,?,'Emprestado',?)",
                             (livro_id, usuario_id, _agora())).lastrowid

    def devolver(self, emprestimo_id):
        with self.banco.conexao() as c:
            c.execute('BEGIN IMMEDIATE')
            registro = c.execute('SELECT id_livro,status FROM emprestimos WHERE id=?', (emprestimo_id,)).fetchone()
            if registro is None:
                raise ErroBiblioteca('Empréstimo não encontrado. Atualize a tela.')
            alterados = c.execute("UPDATE emprestimos SET status='Devolvido',data_devolucao=? WHERE id=? AND status='Emprestado'",
                                 (_agora(), emprestimo_id)).rowcount
            if alterados != 1:
                raise ErroBiblioteca('Este empréstimo já foi devolvido. Atualize a tela.')
            c.execute('UPDATE livros SET copias_disponiveis=copias_disponiveis+1 WHERE id=?', (registro['id_livro'],))

    def listar_livros(self, busca='', somente_disponiveis=False):
        with self.banco.conexao() as c:
            registros = [dict(r) for r in c.execute('''
                SELECT l.*,count(e.id) AS copias_emprestadas,
                       l.copias_disponiveis+count(e.id) AS copias_total
                FROM livros l LEFT JOIN emprestimos e ON e.id_livro=l.id AND e.status='Emprestado'
                GROUP BY l.id ORDER BY l.titulo COLLATE NOCASE,l.id
            ''')]
        if somente_disponiveis:
            registros = [r for r in registros if r['copias_disponiveis'] > 0]
        return _filtrar(registros, busca, ['titulo', 'autor', 'ano'])

    def listar_usuarios(self, busca=''):
        with self.banco.conexao() as c:
            registros = [dict(r) for r in c.execute('''
                SELECT u.*,count(e.id) AS emprestimos_ativos FROM usuarios u
                LEFT JOIN emprestimos e ON e.id_usuario=u.id AND e.status='Emprestado'
                GROUP BY u.id ORDER BY u.nome COLLATE NOCASE,u.id
            ''')]
        return _filtrar(registros, busca, ['nome', 'identificacao', 'contato'])

    def listar_emprestimos(self, status=None):
        if status not in (None, 'Emprestado', 'Devolvido'):
            raise ErroBiblioteca('Status de empréstimo inválido.')
        with self.banco.conexao() as c:
            return [dict(r) for r in c.execute('''
                SELECT e.*,l.titulo,l.autor,u.nome,u.identificacao FROM emprestimos e
                JOIN livros l ON l.id=e.id_livro JOIN usuarios u ON u.id=e.id_usuario
                WHERE (? IS NULL OR e.status=?) ORDER BY e.id DESC
            ''', (status, status))]

    def indicadores(self):
        # Um único SELECT fornece uma visão consistente de todos os indicadores.
        with self.banco.conexao() as c:
            dados = dict(c.execute('''
                SELECT (SELECT COUNT(*) FROM livros) AS titulos,
                (SELECT COALESCE(SUM(copias_disponiveis),0) FROM livros) AS disponiveis,
                (SELECT COUNT(*) FROM emprestimos WHERE status='Emprestado') AS emprestados,
                (SELECT COUNT(*) FROM usuarios) AS usuarios
            ''').fetchone())
        dados['total'] = dados['disponiveis'] + dados['emprestados']
        return dados
