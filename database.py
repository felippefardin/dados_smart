from main import conectar_banco, inicializar_banco

def listar_usuarios():
    inicializar_banco()
    conn = conectar_banco()
    usuarios = conn.execute(
        "SELECT matricula, nome_completo, email, autorizado, tipo_usuario FROM usuarios"
    ).fetchall()
    conn.close()
    if not usuarios:
        print("Nenhum usuário cadastrado.")
        return
    for usuario in usuarios:
        print(usuario)

if __name__ == "__main__":
    listar_usuarios()
