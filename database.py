import sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def inicializar_banco():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
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
    
    # Inserção do usuário padrão (apenas se não existir)
    senha_usuario = pwd_context.hash('admin123456')
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'comum', 0)
        ''', ('103578', '00000000000', 'Seu Nome', 'seuemail@pms.local', senha_usuario))
        print("Usuário 103578 criado com sucesso!")
    except sqlite3.IntegrityError:
        print("Usuário padrão já existe no banco.")

    conn.commit()
    conn.close()

def listar_usuarios():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT matricula, nome_completo, tipo_usuario FROM usuarios")
    usuarios = cursor.fetchall()
    
    print("\n--- Usuários Cadastrados ---")
    for u in usuarios:
        print(f"Matrícula: {u[0]} | Nome: {u[1]} | Tipo: {u[2]}")
    conn.close()

if __name__ == "__main__":
    inicializar_banco()
    listar_usuarios()