from fastapi import FastAPI, Query, HTTPException
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
from passlib.context import CryptContext

# Importação da sua lógica de busca
from integracao import buscar_dados_reais, verificar_feriados_nacionais

# Configuração de Hashing de Senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    senha: str

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

app.post("/auth/login")
async def login(dados: LoginSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    
    # Certifique-se de que a ordem dos campos no SELECT corresponde ao índice user[4]
    # SELECT nome, autorizado, tipo, reset, senha_hash
    cursor.execute("SELECT nome_completo, autorizado, tipo_usuario, senha_resetada, senha_hash FROM usuarios WHERE matricula = ?", 
                   (dados.matricula,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verificar_senha(dados.senha, user[4]):
        raise HTTPException(status_code=401, detail="Matrícula ou senha incorretos.")
    
    # Validação de status (0: Pendente, -1: Negado, 1: Autorizado)
    if user[1] == 0:
        raise HTTPException(status_code=403, detail="Seu cadastro ainda está pendente de aprovação.")
    elif user[1] == -1:
        raise HTTPException(status_code=403, detail="Seu acesso foi negado pelo administrador.")
    elif user[1] != 1:
        raise HTTPException(status_code=403, detail="Acesso desativado pelo administrador.")

    return {
        "msg": "Login realizado com sucesso!",
        "nome": user[0],
        "tipo_usuario": user[2],
        "precisa_mudar_senha": bool(user[3])
    }

# --- GESTÃO MASTER E UTILITÁRIOS ---

@app.get("/admin/feriados")
async def listar_feriados():
    return verificar_feriados_nacionais()

@app.post("/admin/criar-usuario")
async def criar_usuario(dados: UserCreateSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    hash_seguro = gerar_hash(dados.senha)
    try:
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'comum', 1)
        ''', (dados.matricula, dados.matricula, dados.nome_completo, f"{dados.matricula}@pms.local", hash_seguro))
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
    return {
        "nome": "Não Localizado", "documento": documento, "data_nascimento": "N/A",
        "exercicio": ", ".join(exercicio) if exercicio else "N/A",
        "valor_divida": "0,00", "status": "Não Encontrado", "estornado": "N/A", "endereco": "N/A"
    }

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, tipo: Optional[str] = Query(None), exercicio: Optional[List[str]] = Query(None)):
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento", exercicio=exercicio)
    
    html_template = f"""
    <html>
        <body style="font-family: Arial; padding: 20px;">
            <h1 style="color: #4361ee; text-align: center;">DADOS SMART</h1>
            <hr>
            <p><strong>Nome:</strong> {dados.get('nome', 'N/A')}</p>
            <p><strong>Documento:</strong> {dados.get('documento', 'N/A')}</p>
            <p><strong>Dívida:</strong> R$ {dados.get('valor_divida', '0,00')}</p>
            <p style="font-size: 10px; margin-top: 40px;">Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </body>
    </html>
    """
    
    path_pdf = f"relatorio_{documento}.pdf"
    path_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    if not os.path.exists(path_wk):
        raise HTTPException(status_code=500, detail=f"Erro crítico: Executável wkhtmltopdf não encontrado em {path_wk}")

    try:
        config = pdfkit.configuration(wkhtmltopdf=path_wk)
        pdfkit.from_string(html_template, path_pdf, configuration=config, options={'encoding': "UTF-8", 'quiet': ''})
        return FileResponse(path_pdf, media_type='application/pdf', filename=path_pdf)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)