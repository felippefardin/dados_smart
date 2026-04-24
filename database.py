import sqlite3

def criar_banco():
    # Conecta ao arquivo de banco de dados
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Tabela de Usuários (Com matrícula PMS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            cpf TEXT UNIQUE NOT NULL,
            nome_completo TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            celular TEXT,
            data_nascimento TEXT,
            senha_hash TEXT NOT NULL,
            codigo_verificacao TEXT,
            ativo INTEGER DEFAULT 0
        )
    ''')
    
    # Tabela de Logs atualizada com múltiplos exercícios e endereço
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_consulta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            cpf_consultado TEXT,
            exercicios_consultados TEXT, -- Campo para salvar a lista de anos (ex: 2023, 2024)
            endereco_retornado TEXT,      -- Campo para salvar o endereço detalhado da consulta
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()
    print("Banco de dados e tabelas configurados com sucesso.")