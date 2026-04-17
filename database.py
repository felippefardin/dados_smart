import sqlite3

def criar_banco():
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_consulta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            cpf_consultado TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()