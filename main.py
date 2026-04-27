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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Importação da sua lógica de busca
from integracao import buscar_dados_reais

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

@app.post("/auth/login")
async def login(dados: LoginSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    # Busca incluindo a coluna senha_resetada e status de autorização
    cursor.execute("SELECT nome_completo, autorizado, tipo_usuario, senha_resetada FROM usuarios WHERE matricula = ? AND senha_hash = ?", 
                   (dados.matricula, dados.senha))
    user = cursor.fetchone()
    conn.close()

    if not user:
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

# --- GESTÃO MASTER (USUÁRIOS) ---

@app.post("/admin/criar-usuario")
async def criar_usuario(dados: UserCreateSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    try:
        # Criado com senha_resetada=1 para forçar troca no primeiro acesso
        # CPF é preenchido com a matrícula por padrão nesta rota simplificada
        cursor.execute('''
            INSERT INTO usuarios (matricula, cpf, nome_completo, email, senha_hash, autorizado, tipo_usuario, senha_resetada)
            VALUES (?, ?, ?, ?, ?, 1, 'comum', 1)
        ''', (dados.matricula, dados.matricula, dados.nome_completo, f"{dados.matricula}@pms.local", dados.senha))
        conn.commit()
        return {"msg": "Usuário criado com sucesso!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada.")
    finally:
        conn.close()

@app.get("/admin/listar-usuarios")
async def listar_usuarios():
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, matricula, nome_completo FROM usuarios WHERE tipo_usuario = 'comum'")
    usuarios = cursor.fetchall()
    conn.close()
    return [{"id": u[0], "matricula": u[1], "nome": u[2]} for u in usuarios]

@app.delete("/admin/usuario/{user_id}")
async def remover_usuario(user_id: int):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ? AND tipo_usuario != 'master'", (user_id,))
    conn.commit()
    conn.close()
    return {"msg": "Usuário removido com sucesso!"}

@app.post("/admin/reset-senha/{user_id}")
async def resetar_senha_usuario(user_id: int):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET senha_hash = 'pms123', senha_resetada = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"msg": "Senha resetada para: pms123. O usuário deverá alterá-la no próximo acesso."}

@app.post("/auth/definir-nova-senha")
async def definir_nova_senha(dados: NovaSenhaSchema):
    conn = sqlite3.connect('dados_smart.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET senha_hash = ?, senha_resetada = 0 WHERE matricula = ?", 
                   (dados.nova_senha, dados.matricula))
    conn.commit()
    conn.close()
    return {"msg": "Senha atualizada com sucesso!"}

# --- CONSULTAS E RELATÓRIOS ---

@app.get("/consultar")
async def consultar_documento(
    documento: str = Query(...), 
    tipo: str = Query("documento"),
    exercicio: Optional[List[str]] = Query(None)
):
    dados = buscar_dados_reais(documento, exercicio)
    if dados:
        return dados
    return {
        "nome": "Não Localizado",
        "documento": documento,
        "data_nascimento": "N/A",
        "exercicio": ", ".join(exercicio) if exercicio else "N/A",
        "valor_divida": "0,00",
        "status": "Não Encontrado",
        "estornado": "N/A",
        "endereco": "N/A"
    }

@app.get("/gerar-excel/{documento}")
async def gerar_excel_rota(
    documento: str, 
    tipo: Optional[str] = Query(None), 
    exercicio: Optional[List[str]] = Query(None)
):
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento", exercicio=exercicio)
    
    registro = {
        "Nome/Razão Social": dados.get("nome", "N/A"),
        "CPF/CNPJ": dados.get("documento", documento),
        "Data de Nascimento": dados.get("data_nascimento", "N/A"),
        "Exercícios": dados.get("exercicio", "N/A"),
        "Endereço Completo": dados.get("endereco", "N/A"),
        "Valor da Dívida (R$)": dados.get("valor_divida", "0,00"),
        "Situação/Status": dados.get("status", "N/A"),
        "Estornado": dados.get("estornado", "Não")
    }
    
    df = pd.DataFrame([registro])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio Dados Smart')
    
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{documento}.xlsx"}
    )

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, tipo: Optional[str] = Query(None), exercicio: Optional[List[str]] = Query(None)):
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento", exercicio=exercicio)
    endereco_final = dados.get('endereco') or "Não informado"

    html_template = f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Helvetica', Arial, sans-serif; color: #333; line-height: 1.6; }}
                .header {{ text-align: center; border-bottom: 2px solid #4361ee; padding-bottom: 10px; }}
                .title {{ color: #4361ee; font-size: 24px; margin-bottom: 5px; }}
                .container {{ padding: 20px; }}
                .info-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                .info-table th, .info-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                .info-table th {{ background-color: #f8fafc; color: #64748b; font-size: 12px; text-transform: uppercase; }}
                .footer {{ margin-top: 30px; font-size: 10px; text-align: center; color: #777; }}
                .status-badge {{ padding: 5px 10px; border-radius: 4px; background: #e0e7ff; color: #4361ee; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="title">DADOS SMART</div>
                <div>Relatório de Consulta Integrada</div>
            </div>
            <div class="container">
                <table class="info-table">
                    <tr><th colspan="2">Informações do Contribuinte</th></tr>
                    <tr><td><strong>Nome/Razão Social:</strong></td><td>{dados.get('nome', 'N/A')}</td></tr>
                    <tr><td><strong>Documento (CPF/CNPJ):</strong></td><td>{dados.get('documento', 'N/A')}</td></tr>
                    <tr><td><strong>Data de Nascimento:</strong></td><td>{dados.get('data_nascimento', 'N/A')}</td></tr>
                    <tr><td><strong>Endereço:</strong></td><td>{endereco_final}</td></tr>
                </table>
                <table class="info-table" style="margin-top: 30px;">
                    <tr><th colspan="2">Detalhes Financeiros / Dívida Ativa</th></tr>
                    <tr><td><strong>Exercícios:</strong></td><td>{dados.get('exercicio', 'N/A')}</td></tr>
                    <tr><td><strong>Valor da Dívida:</strong></td><td>R$ {dados.get('valor_divida', '0,00')}</td></tr>
                    <tr><td><strong>Situação/Status:</strong></td><td><span class="status-badge">{dados.get('status', 'N/A')}</span></td></tr>
                    <tr><td><strong>Estornado:</strong></td><td>{dados.get('estornado', 'N/A')}</td></tr>
                </table>
            </div>
            <div class="footer">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>
        </body>
    </html>
    """
    
    path_pdf = f"relatorio_{documento}.pdf"
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    try:
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        options = {'encoding': "UTF-8", 'quiet': ''}
        pdfkit.from_string(html_template, path_pdf, configuration=config, options=options)
        return FileResponse(path_pdf, media_type='application/pdf', filename=path_pdf)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)