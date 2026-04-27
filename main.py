from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import pdfkit
import os
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações de E-mail
EMAIL_PADRAO = "felippefardin@gmail.com"
SENHA_APP = "iypl fxqa oxjl dqzn"

# Modelos de Dados
class UserCreate(BaseModel):
    matricula: str
    cpf: str
    nome_completo: str
    email: str
    celular: str
    data_nascimento: str
    senha: str

class LoginSchema(BaseModel):
    matricula: str
    senha: str

app = FastAPI(title="Dados Smart - Integrador")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Função Utilitária para Enviar E-mail
def enviar_email(destinatario, assunto, corpo):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_PADRAO, SENHA_APP)
        msg = MIMEMultipart()
        msg['From'] = EMAIL_PADRAO
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'html'))
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# --- ROTAS DE AUTENTICAÇÃO ---

@app.post("/auth/login")
async def login(dados: LoginSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nome_completo, autorizado, tipo_usuario FROM usuarios WHERE matricula = ? AND senha_hash = ?", 
                   (dados.matricula, dados.senha))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Matrícula ou senha incorretos.")
    
    if user[1] == 0:
        raise HTTPException(status_code=403, detail="Seu cadastro ainda está pendente de aprovação.")
    elif user[1] == -1:
        raise HTTPException(status_code=403, detail="Seu acesso foi negado pelo administrador.")

    return {
        "msg": "Login realizado com sucesso!",
        "nome": user[0],
        "tipo_usuario": user[2]
    }

@app.post("/auth/cadastrar")
async def cadastrar_usuario(dados: UserCreate):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, whatsapp, data_nascimento, senha_hash, autorizado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (dados.matricula, dados.cpf, dados.nome_completo, dados.email, dados.celular, dados.data_nascimento, dados.senha))
        user_id = cursor.lastrowid
        conn.commit()

        # Notifica o Master
        link_aprovar = f"http://127.0.0.1:8000/auth/aprovar/{user_id}?acao=1"
        link_negar = f"http://127.0.0.1:8000/auth/aprovar/{user_id}?acao=-1"
        
        corpo = f"<h3>Novo Cadastro: {dados.nome_completo}</h3><p>Matrícula: {dados.matricula}</p>" \
                f"<a href='{link_aprovar}'>AUTORIZAR</a> | <a href='{link_negar}'>NEGAR</a>"
        enviar_email(EMAIL_PADRAO, "Novo Usuário Pendente", corpo)
        
        return {"msg": "Cadastro enviado! Aguarde a aprovação do administrador por e-mail."}
    except Exception:
        raise HTTPException(status_code=400, detail="Erro ao cadastrar. Matrícula ou E-mail já existem.")
    finally:
        conn.close()

@app.get("/auth/aprovar/{user_id}")
async def aprovar_usuario(user_id: int, acao: int):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, nome_completo FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user: return "Usuário não encontrado."

    if acao == 1:
        cursor.execute("UPDATE usuarios SET autorizado = 1 WHERE id = ?", (user_id,))
        enviar_email(user[0], "Acesso Liberado", f"Olá {user[1]}, seu acesso foi autorizado!")
        msg = "Usuário autorizado."
    else:
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        enviar_email(user[0], "Acesso Negado", f"Olá {user[1]}, seu cadastro não foi autorizado e foi removido.")
        msg = "Usuário negado e removido."
    
    conn.commit()
    conn.close()
    return msg

@app.get("/admin/usuarios-pendentes")
async def listar_pendentes():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_completo, matricula, email FROM usuarios WHERE autorizado = 0")
    usuarios = cursor.fetchall()
    conn.close()
    return [{"id": u[0], "nome": u[1], "matricula": u[2], "email": u[3]} for u in usuarios]

# --- ROTAS DE NEGÓCIO (CONSULTA / EXPORTAÇÃO) ---

@app.get("/consultar")
async def consultar(documento: str, tipo: str = "documento"):
    # Sua lógica de integração aqui
    return {"nome": "Exemplo", "documento": documento, "status": "Ativa", "valor_divida": "0,00"}

@app.get("/gerar-excel/{documento}")
async def excel(documento: str):
    # Lógica simplificada de Excel
    df = pd.DataFrame([{"Documento": documento, "Status": "Ativa"}])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.ms-excel", headers={"Content-Disposition": f"attachment; filename=relatorio.xlsx"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)