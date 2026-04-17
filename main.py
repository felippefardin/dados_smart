import smtplib
from email.mime.text import MIMEText
from integracao import buscar_dados_reais
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional
from passlib.context import CryptContext
import sqlite3
import pdfkit
from jinja2 import Template
import os
import re
import random
from datetime import datetime

app = FastAPI(title="Dados Smart - Integrador")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DE E-MAIL ---
def enviar_email_real(destinatario, codigo, assunto="Código de Verificação - Dados Smart"):
    remetente = "contatotech.tecnologia@gmail.com" 
    senha = "tvla qhnf vqts qvsu" 
    
    corpo = f"Seu código para o sistema Dados Smart é: {codigo}"
    msg = MIMEText(corpo)
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

def validar_senha(senha: str):
    if len(senha) < 8: return False
    if not re.search("[a-z]", senha): return False
    if not re.search("[A-Z]", senha): return False
    if not re.search("[0-9]", senha): return False
    if not re.search("[!@#$%^&*(),.?\":{}|<>]", senha): return False
    return True

# --- ROTAS DE AUTENTICAÇÃO ---
@app.post("/auth/cadastrar")
async def cadastrar(dados: dict = Body(...)):
    if not validar_senha(dados['senha']):
        raise HTTPException(status_code=400, detail="Senha fraca: use 8+ caracteres, maiúsculas, minúsculas, números e símbolos.")
    
    codigo = str(random.randint(100000, 999999))

    # PEGA O EMAIL DIRETAMENTE DO DICIONÁRIO 'DADOS' ENVIADO PELO FRONTEND
    destinatario_usuario = dados.get('email')
    email_enviado = enviar_email_real(destinatario_usuario, codigo, "Ative sua conta - Dados Smart")
    
    # Envio Real de E-mail
    if not enviar_email_real(dados['email'], codigo, "Ative sua conta - Dados Smart"):
        print(f"--- FALHA NO SMTP. CÓDIGO NO TERMINAL: {codigo} ---")

    try:
        senha_hash = pwd_context.hash(dados['senha'])
        conn = sqlite3.connect('dados_smart.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO usuarios (matricula, cpf, nome_completo, email, celular, data_nascimento, senha_hash, codigo_verificacao) 
                          VALUES (?,?,?,?,?,?,?,?)''', 
                       (dados['matricula'], dados['cpf'], dados['nome_completo'], dados['email'], dados['celular'], dados['data_nascimento'], senha_hash, codigo))
        conn.commit()
        return {"status": "sucesso", "msg": "Código enviado ao e-mail!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Matrícula, CPF ou E-mail já cadastrados.")
    finally:
        conn.close()

@app.post("/auth/login")
async def login(dados: dict = Body(...)):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT senha_hash, nome_completo, data_nascimento FROM usuarios WHERE matricula = ? AND ativo = 1", (dados['matricula'],))
    user = cursor.fetchone()
    conn.close()

    if user and pwd_context.verify(dados['senha'], user[0]):
        hoje = datetime.now().strftime("%m-%d")
        try:
            aniv = datetime.strptime(user[2], "%Y-%m-%d").strftime("%m-%d") if user[2] else ""
        except:
            aniv = ""
        return {"status": "sucesso", "nome": user[1], "aniversario": (hoje == aniv), "msg": "Bem vindo ao sistema!"}
    raise HTTPException(status_code=401, detail="Credenciais incorretas ou conta inativa.")

# (Manter rotas de relatórios e PDF originais abaixo)