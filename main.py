from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import pandas as pd
import sqlite3
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações de E-mail
EMAIL_PADRAO = "felippefardin@gmail.com"
SENHA_APP = "iypl fxqa oxjl dqzn"

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
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, whatsapp, data_nascimento, senha_hash, autorizado, tipo_usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'comum')
        ''', (dados.matricula, dados.cpf, dados.nome_completo, dados.email, dados.celular, dados.data_nascimento, dados.senha))
        user_id = cursor.lastrowid
        conn.commit()

        # Notifica o Master por e-mail com links rápidos
        link_aprovar = f"http://127.0.0.1:8000/auth/aprovar/{user_id}?acao=1"
        link_negar = f"http://127.0.0.1:8000/auth/aprovar/{user_id}?acao=-1"
        
        corpo = f"<h3>Novo Cadastro Pendente</h3><p><b>Nome:</b> {dados.nome_completo}</p><p><b>Matrícula:</b> {dados.matricula}</p>" \
                f"<p><a href='{link_aprovar}' style='background:green;color:white;padding:10px;text-decoration:none;'>AUTORIZAR ACESSO</a></p>" \
                f"<p><a href='{link_negar}' style='background:red;color:white;padding:10px;text-decoration:none;'>NEGAR E REMOVER</a></p>"
        enviar_email(EMAIL_PADRAO, "Novo Usuário no Sistema", corpo)
        
        return {"msg": "Cadastro enviado! Aguarde a aprovação."}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Erro ao cadastrar. Verifique se os dados já existem.")
    finally:
        conn.close()

@app.get("/auth/aprovar/{user_id}")
async def aprovar_usuario(user_id: int, acao: int):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, nome_completo FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user: 
        conn.close()
        return "Usuário não encontrado."

    if acao == 1:
        cursor.execute("UPDATE usuarios SET autorizado = 1 WHERE id = ?", (user_id,))
        enviar_email(user[0], "Acesso Liberado - Dados Smart", f"Olá {user[1]}, seu acesso foi autorizado! Já pode logar.")
        msg = "Usuário autorizado com sucesso."
    else:
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        enviar_email(user[0], "Cadastro Indeferido", f"Olá {user[1]}, seu cadastro não foi autorizado.")
        msg = "Solicitação removida."
    
    conn.commit()
    conn.close()
    return msg

@app.get("/admin/usuarios-pendentes")
async def listar_pendentes():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    # Adicionado o campo 'id' na busca para o JavaScript poder usar
    cursor.execute("SELECT id, matricula, nome_completo, email FROM usuarios WHERE autorizado = 0")
    usuarios = cursor.fetchall()
    conn.close()
    return [{"id": u[0], "matricula": u[1], "nome": u[2], "email": u[3]} for u in usuarios]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)