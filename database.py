import sqlite3
from passlib.context import CryptContext

# Define o contexto de hash para segurança da senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def criar_banco():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Cria a tabela de usuários
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
            autorizado INTEGER DEFAULT 0,
            tipo_usuario TEXT DEFAULT 'comum',
            senha_resetada INTEGER DEFAULT 0
        )
    ''')
    
    # Gera o hash da senha 'admin123456'
    senha_usuario = pwd_context.hash('admin123456')
    
    # Insere o seu usuário
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'comum', 0)
        ''', ('103578', '00000000000', 'Seu Nome', 'seuemail@pms.local', senha_usuario))
        print("Usuário 103578 criado com sucesso!")
    except sqlite3.IntegrityError:
        print("Usuário já existe no banco.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()