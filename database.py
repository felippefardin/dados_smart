import sqlite3

def criar_banco():
    # Conecta ao banco (será criado do zero se você deletou o antigo)
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Criar tabela de usuários com todas as colunas necessárias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            cpf TEXT UNIQUE NOT NULL,
            nome_completo TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            whatsapp TEXT,
            data_nascimento TEXT,
            senha_hash TEXT NOT NULL,
            autorizado INTEGER DEFAULT 0, -- 0: Pendente, 1: Autorizado, -1: Negado
            tipo_usuario TEXT DEFAULT 'comum' -- 'comum' ou 'master'
        )
    ''')
    
    # Criar tabela de logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_consulta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            cpf_consultado TEXT,
            exercicios_consultados TEXT,
            endereco_retornado TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Inserir o usuário MASTER padrão para o seu primeiro acesso
    cursor.execute("SELECT * FROM usuarios WHERE email = 'felippefardin@gmail.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario)
            VALUES ('MASTER', '00000000000', 'Felippe Master', 'felippefardin@gmail.com', 'admin123', 1, 'master')
        ''')
        print("Usuário MASTER criado com sucesso!")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()
    print("Banco de dados configurado do zero com sucesso.")