-- Estrutura da versão 1. Referência; a aplicação gerencia a criação e migração.
PRAGMA foreign_keys = ON;

CREATE TABLE livros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL CHECK(length(trim(titulo)) > 0),
        autor TEXT NOT NULL CHECK(length(trim(autor)) > 0),
        ano INTEGER NOT NULL CHECK(typeof(ano)='integer' AND ano BETWEEN 1 AND 9999),
        copias_disponiveis INTEGER NOT NULL
            CHECK(typeof(copias_disponiveis)='integer' AND copias_disponiveis >= 0)
    );

CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL CHECK(length(trim(nome)) > 0),
        identificacao TEXT UNIQUE NOT NULL CHECK(length(trim(identificacao)) > 0),
        contato TEXT NOT NULL CHECK(length(trim(contato)) > 0)
    );

CREATE TABLE emprestimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_livro INTEGER NOT NULL REFERENCES livros(id) ON DELETE RESTRICT,
        id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
        status TEXT NOT NULL DEFAULT 'Emprestado' CHECK(status IN ('Emprestado','Devolvido')),
        data_emprestimo TEXT,
        data_devolucao TEXT,
        CHECK(status='Devolvido' OR data_devolucao IS NULL)
    );

CREATE INDEX idx_emprestimos_livro ON emprestimos(id_livro);

CREATE INDEX idx_emprestimos_usuario ON emprestimos(id_usuario);

CREATE INDEX idx_emprestimos_status ON emprestimos(status);
PRAGMA user_version = 1;
