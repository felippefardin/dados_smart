import sqlite3
from passlib.context import CryptContext

# Define o contexto de hash
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def criar_banco():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Cria as tabelas
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
    
    # Gera o hash da senha 'admin123'
    senha_segura = pwd_context.hash('admin123')

    # Verifica se o master já existe
    cursor.execute("SELECT * FROM usuarios WHERE email = 'felippefardin@gmail.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'master', 0)
        ''', ('MASTER', '00000000000', 'Felippe Master', 'felippefardin@gmail.com', senha_segura))
        print("Usuário MASTER criado com senha criptografada!")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()