import sqlite3

def adicionar_coluna():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna senha_resetada à tabela usuarios
        cursor.execute("ALTER TABLE usuarios ADD COLUMN senha_resetada INTEGER DEFAULT 0")
        conn.commit()
        print("Coluna 'senha_resetada' adicionada com sucesso!")
    except sqlite3.OperationalError:
        # Se a coluna já existir, o sqlite retornará um erro que podemos ignorar
        print("A coluna 'senha_resetada' já existe ou a tabela não foi encontrada.")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_coluna()