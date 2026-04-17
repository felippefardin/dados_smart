import sqlite3

def criar_banco():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Tabela para configurar quais campos a API deles oferece
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campos_disponiveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campo_chave TEXT NOT NULL,
            label_amigavel TEXT NOT NULL
        )
    ''')
    
    # Tabela de Auditoria (Essencial para Segurança/LGPD)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_consulta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            cpf_consultado TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inserindo alguns campos de exemplo para sua interface
    campos = [
        ('nome', 'Nome Completo'),
        ('valor_divida', 'Valor do Débito'),
        ('data_vencimento', 'Data de Vencimento'),
        ('status', 'Situação Atual')
    ]
    cursor.executemany('INSERT OR IGNORE INTO campos_disponiveis (campo_chave, label_amigavel) VALUES (?,?)', campos)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_banco()