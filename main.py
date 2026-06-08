from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import pdfkit
import os
import sqlite3
from datetime import datetime
from passlib.context import CryptContext

# Importação da sua lógica de busca
from integracao import buscar_dados_reais, verificar_feriados_nacionais

# Configuração de Hashing de Senha
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def gerar_hash(senha: str):
    return pwd_context.hash(senha)

def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)

# --- MODELOS DE DADOS ---

class LoginSchema(BaseModel):
    matricula: str
    senha: str

class UserCreateSchema(BaseModel):
    nome_completo: str
    matricula: str
    cpf: str
    email: str
    celular: str
    data_nascimento: str
    senha: str

class VerificacaoSchema(BaseModel):
    email: str
    codigo: str

class NovaSenhaSchema(BaseModel):
    matricula: str
    nova_senha: str

app = FastAPI(title="Dados Smart - Integrador")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTENTICAÇÃO E LOGIN ---

@app.post("/auth/login")
async def login(dados: LoginSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nome_completo, autorizado, tipo_usuario, senha_resetada, senha_hash FROM usuarios WHERE matricula = ?", 
                   (dados.matricula,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verificar_senha(dados.senha, user[4]):
        raise HTTPException(status_code=401, detail="Matrícula ou senha incorretos.")
    
    if user[1] == 0:
        raise HTTPException(status_code=403, detail="Cadastro pendente de aprovação.")
    
    return {
        "msg": "Login realizado com sucesso!",
        "nome": user[0],
        "tipo_usuario": user[2],
        "precisa_mudar_senha": bool(user[3])
    }

# --- CADASTRO E VERIFICAÇÃO ---

@app.post("/auth/cadastrar")
async def cadastrar(dados: UserCreateSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    hash_seguro = gerar_hash(dados.senha)
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario)
            VALUES (?, ?, ?, ?, ?, 0, 'comum')
        ''', (dados.matricula, dados.cpf, dados.nome_completo, dados.email, hash_seguro))
        conn.commit()
        return {"msg": "Usuário pré-cadastrado! Aguarde aprovação."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Matrícula ou CPF já cadastrados.")
    finally:
        conn.close()

@app.post("/auth/verificar-cadastro")
async def verificar_cadastro(dados: VerificacaoSchema):
    # Lógica de validação de código fictícia para o seu fluxo
    return {"msg": "Cadastro verificado!"}

# --- GESTÃO MASTER E UTILITÁRIOS ---

@app.get("/admin/feriados")
async def listar_feriados():
    return verificar_feriados_nacionais()

@app.post("/admin/criar-usuario")
async def criar_usuario(dados: NovaSenhaSchema): # Ajuste conforme necessário
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    hash_seguro = gerar_hash(dados.nova_senha)
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'comum', 1)
        ''', (dados.matricula, dados.matricula, "Novo Usuário", f"{dados.matricula}@pms.local", hash_seguro))
        conn.commit()
        return {"msg": "Usuário criado com sucesso!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada.")
    finally:
        conn.close()

@app.post("/auth/definir-nova-senha")
async def definir_nova_senha(dados: NovaSenhaSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    novo_hash = gerar_hash(dados.nova_senha)
    cursor.execute("UPDATE usuarios SET senha_hash = ?, senha_resetada = 0 WHERE matricula = ?", 
                   (novo_hash, dados.matricula))
    conn.commit()
    conn.close()
    return {"msg": "Senha atualizada com sucesso!"}

# --- CONSULTAS E RELATÓRIOS ---

@app.get("/consultar")
async def consultar_documento(documento: str = Query(...), tipo: str = Query("documento"), exercicio: Optional[List[str]] = Query(None)):
    dados = buscar_dados_reais(documento, exercicio)
    if dados: return dados
    return {"nome": "Não Localizado", "documento": documento, "valor_divida": "0,00", "status": "Não Encontrado"}

class EsqueciSenhaSchema(BaseModel):
    email: str
    
@app.post("/auth/esqueci-senha")
async def esqueci_senha(dados: EsqueciSenhaSchema):
    # Aqui você implementaria o envio do e-mail
    return {"msg": "Código enviado para o e-mail!"}

@app.post("/auth/redefinir-senha")
async def redefinir_senha(dados: dict): # Simplificado para teste
    # Lógica para redefinir a senha
    return {"msg": "Senha redefinida com sucesso!"}

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, tipo: Optional[str] = Query(None)):
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento")
    
    html_template = f"""
    <html><body>
        <h1>DADOS SMART</h1>
        <p><strong>Nome:</strong> {dados.get('nome', 'N/A')}</p>
        <p><strong>Dívida:</strong> R$ {dados.get('valor_divida', '0,00')}</p>
    </body></html>
    """
    path_pdf = f"relatorio_{documento}.pdf"
    path_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    config = pdfkit.configuration(wkhtmltopdf=path_wk)
    pdfkit.from_string(html_template, path_pdf, configuration=config)
    return FileResponse(path_pdf, media_type='application/pdf', filename=path_pdf)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)