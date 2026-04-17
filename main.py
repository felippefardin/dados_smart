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

from email.mime.text import MIMEText

def enviar_email_real(destinatario, codigo):
    # Configurações do seu e-mail (Exemplo Gmail)
    remetente = "seu-email@gmail.com"
    senha = "sua-senha-de-app" # Não é a senha normal, é uma senha de aplicativo gerada na conta Google
    
    msg = MIMEText(f"Seu código de verificação para o Dados Smart é: {codigo}")
    msg['Subject'] = 'Código de Verificação - Dados Smart'
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

# --- SEGURANÇA ---
def validar_senha(senha: str):
    # Acima de 8, maiúscula, minúscula, número e especial
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
        raise HTTPException(status_code=400, detail="A senha deve ter 8+ caracteres, letras maiúsculas, minúsculas, números e caracteres especiais.")
    
    senha_hash = pwd_context.hash(dados['senha'])
    codigo = str(random.randint(100000, 999999))
    
    try:
        conn = sqlite3.connect('dados_smart.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO usuarios (matricula, cpf, nome_completo, email, celular, data_nascimento, senha_hash, codigo_verificacao) 
                          VALUES (?,?,?,?,?,?,?,?)''', 
                       (dados['matricula'], dados['cpf'], dados['nome_completo'], dados['email'], dados['celular'], dados['data_nascimento'], senha_hash, codigo))
        conn.commit()
        # Aqui você integraria com um serviço de e-mail real
        print(f"CÓDIGO DE ATIVAÇÃO PARA {dados['email']}: {codigo}")
        return {"status": "sucesso", "msg": "Código enviado ao e-mail!", "codigo_teste": codigo}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Matrícula, CPF ou E-mail já cadastrados.")
    finally:
        conn.close()

@app.post("/auth/verificar-cadastro")
async def verificar_cadastro(dados: dict = Body(...)):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = ? AND codigo_verificacao = ?", (dados['email'], dados['codigo']))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE usuarios SET ativo = 1, codigo_verificacao = NULL WHERE id = ?", (user[0],))
        conn.commit()
        return {"status": "sucesso", "msg": "Cadastro realizado com sucesso!"}
    raise HTTPException(status_code=400, detail="Código de verificação inválido.")

@app.post("/auth/login")
async def login(dados: dict = Body(...)):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT senha_hash, nome_completo, data_nascimento FROM usuarios WHERE matricula = ? AND ativo = 1", (dados['matricula'],))
    user = cursor.fetchone()
    conn.close()

    if user and pwd_context.verify(dados['senha'], user[0]):
        # Lógica de Aniversário
        hoje = datetime.now().strftime("%m-%d")
        # Assume-se data_nascimento no formato YYYY-MM-DD
        aniv = user[2][5:] if user[2] else ""
        is_birthday = (hoje == aniv)
        
        return {
            "status": "sucesso", 
            "nome": user[1], 
            "aniversario": is_birthday,
            "msg": "Bem vindo ao sistema!"
        }
    raise HTTPException(status_code=401, detail="Matrícula ou senha incorretos ou conta não ativada.")

@app.post("/auth/esqueci-senha")
async def esqueci_senha(dados: dict = Body(...)):
    codigo = str(random.randint(100000, 999999))
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET codigo_verificacao = ? WHERE email = ?", (codigo, dados['email']))
    if cursor.rowcount > 0:
        conn.commit()
        print(f"CÓDIGO DE RECUPERAÇÃO PARA {dados['email']}: {codigo}")
        return {"status": "sucesso", "codigo_teste": codigo}
    raise HTTPException(status_code=404, detail="E-mail não encontrado.")

@app.post("/auth/redefinir-senha")
async def redefinir_senha(dados: dict = Body(...)):
    if not validar_senha(dados['nova_senha']):
        raise HTTPException(status_code=400, detail="Nova senha não atende aos requisitos.")
    
    nova_hash = pwd_context.hash(dados['nova_senha'])
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET senha_hash = ?, codigo_verificacao = NULL WHERE email = ? AND codigo_verificacao = ?", 
                   (nova_hash, dados['email'], dados['codigo']))
    if cursor.rowcount > 0:
        conn.commit()
        return {"status": "sucesso", "msg": "Senha redefinida com sucesso!"}
    raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

# --- (Mantive as rotas de relatório e PDF abaixo) ---
@app.get("/gerar-relatorio")
async def gerar_relatorio(documento: str, campos_selecionados: Optional[str] = Query(None)):
    dados_brutos = buscar_dados_reais(documento)
    if dados_brutos is None: dados_brutos = mock_api_externa(documento)
    # ... (restante do código original)
    return dados_brutos

@app.get("/gerar-pdf")
async def gerar_pdf(documento: str, campos_selecionados: Optional[str] = Query(None)):
    # ... (código original do PDF)
    return FileResponse(...)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)