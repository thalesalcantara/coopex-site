PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS site_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    valor TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS partner (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '#',
    logo TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    ordem INTEGER NOT NULL DEFAULT 0,
    cliques INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT
);

CREATE INDEX IF NOT EXISTS idx_partner_ativo_ordem ON partner (ativo, ordem, nome);

CREATE TABLE IF NOT EXISTS card_link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    subtitulo TEXT,
    url TEXT NOT NULL DEFAULT '#',
    icone TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    ordem INTEGER NOT NULL DEFAULT 0,
    cliques INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT
);

CREATE INDEX IF NOT EXISTS idx_card_link_ativo_ordem ON card_link (ativo, ordem, criado_em);

CREATE TABLE IF NOT EXISTS site_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_acessos INTEGER NOT NULL DEFAULT 0,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    empresa TEXT,
    comentario TEXT NOT NULL,
    nota INTEGER NOT NULL DEFAULT 5,
    data_avaliacao TEXT,
    link TEXT,
    foto TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    ordem INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_ativo_ordem ON review (ativo, ordem, criado_em);

CREATE TABLE IF NOT EXISTS candidato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_completo TEXT NOT NULL,
    data_nascimento TEXT NOT NULL,
    idade INTEGER NOT NULL,
    escolaridade TEXT NOT NULL,
    email TEXT NOT NULL,
    atividade_remunerada INTEGER NOT NULL DEFAULT 0,
    curriculo TEXT,
    criado_em TEXT
);

CREATE INDEX IF NOT EXISTS idx_candidato_criado_em ON candidato (criado_em DESC);

CREATE TABLE IF NOT EXISTS admin_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_upload (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_filename TEXT,
    mimetype TEXT NOT NULL DEFAULT 'application/octet-stream',
    categoria TEXT,
    tamanho INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT
);

CREATE TABLE IF NOT EXISTS file_chunk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    parte INTEGER NOT NULL,
    data BLOB NOT NULL,
    FOREIGN KEY (file_id) REFERENCES file_upload(id) ON DELETE CASCADE,
    UNIQUE (file_id, parte)
);

CREATE INDEX IF NOT EXISTS idx_file_chunk_file_parte ON file_chunk (file_id, parte);
