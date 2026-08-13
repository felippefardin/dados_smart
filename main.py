from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from passlib.context import CryptContext
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
import hashlib
import os
import pdfkit
import re
import secrets
import smtplib
import pymysql
import ssl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_env_local():
    caminho = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip())

carregar_env_local()
from integracao import buscar_dados_reais, verificar_feriados_nacionais, diagnosticar_integracoes

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
app = FastAPI(title="Dados Smart - Integrador")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

class LoginSchema(BaseModel):
    matricula: str
    senha: str

class UserCreateSchema(BaseModel):
    nome_completo: str
    matricula: str
    cpf: str
    email: str
    celular: str = ""
    data_nascimento: str = ""
    senha: str

class VerificacaoSchema(BaseModel):
    email: str
    codigo: str

class NovaSenhaSchema(BaseModel):
    matricula: str
    nova_senha: str

class EsqueciSenhaSchema(BaseModel):
    email: str

class RedefinirSenhaSchema(BaseModel):
    email: str
    codigo: str
    nova_senha: str

def conectar_banco():
    class ConexaoMySQL:
        def __init__(self):
            self.conexao = pymysql.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=int(os.getenv("DB_PORT", "3306")),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "dados_smart"),
                charset="utf8mb4",
                autocommit=False,
            )
        def execute(self, sql, parametros=()):
            cursor = self.conexao.cursor()
            cursor.execute(sql.replace("?", "%s"), parametros)
            return cursor
        def commit(self): self.conexao.commit()
        def rollback(self): self.conexao.rollback()
        def close(self): self.conexao.close()
    return ConexaoMySQL()

def inicializar_banco():
    conn = conectar_banco()
    conn.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT, matricula VARCHAR(50) UNIQUE NOT NULL,
        cpf VARCHAR(20) UNIQUE NOT NULL, nome_completo VARCHAR(150) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL,
        whatsapp VARCHAR(30), data_nascimento DATE, senha_hash VARCHAR(255) NOT NULL,
        autorizado TINYINT(1) DEFAULT 0, tipo_usuario VARCHAR(30) DEFAULT 'comum', senha_resetada TINYINT(1) DEFAULT 0
    )''')
    for tabela in ("codigos_cadastro", "recuperacoes_senha"):
        conn.execute(f'''CREATE TABLE IF NOT EXISTS {tabela} (
            id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT, email VARCHAR(255) NOT NULL, codigo_hash CHAR(64) NOT NULL,
            expira_em DATETIME NOT NULL, usado TINYINT(1) NOT NULL DEFAULT 0,
            tentativas TINYINT UNSIGNED NOT NULL DEFAULT 0
        )''')
    conn.commit()
    conn.close()

def senha_e_forte(senha):
    return (len(senha) >= 8 and re.search(r"[a-z]", senha) and re.search(r"[A-Z]", senha)
            and re.search(r"\d", senha) and re.search(r"[^A-Za-z0-9]", senha))

def gerar_hash(senha):
    return pwd_context.hash(senha)

def gerar_codigo():
    return f"{secrets.randbelow(1000000):06d}"

def enviar_codigo_email(destinatario, codigo, assunto, introducao):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASSWORD")
    remetente = os.getenv("SMTP_FROM") or usuario
    if not all((host, usuario, senha, remetente)):
        raise RuntimeError("SMTP não configurado")
    destinatario_entrega = destinatario
    if destinatario.lower() == usuario.lower() and destinatario.lower().endswith("@gmail.com"):
        nome, dominio = destinatario.split("@", 1)
        destinatario_entrega = f"{nome}+dadossmart@{dominio}"
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = remetente
    mensagem["To"] = destinatario_entrega
    mensagem.set_content(f"{introducao}: {codigo}\n\nO código expira em 15 minutos.")
    contexto = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as servidor:
        servidor.ehlo()
        servidor.starttls(context=contexto)
        servidor.ehlo()
        servidor.login(usuario, senha)
        servidor.send_message(mensagem)

def salvar_codigo(conn, tabela, email, codigo):
    hash_codigo = hashlib.sha256(codigo.encode()).hexdigest()
    expira = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(tzinfo=None)
    conn.execute(f"UPDATE {tabela} SET usado = 1 WHERE lower(email) = ?", (email,))
    conn.execute(f"INSERT INTO {tabela} (email, codigo_hash, expira_em) VALUES (?, ?, ?)",
                 (email, hash_codigo, expira))

def validar_codigo(conn, tabela, email, codigo):
    registro = conn.execute(f'''SELECT id, codigo_hash, expira_em, tentativas FROM {tabela}
        WHERE lower(email) = ? AND usado = 0 ORDER BY id DESC LIMIT 1''', (email,)).fetchone()
    if not registro:
        conn.close()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    codigo_id, esperado, expira_em, tentativas = registro
    if isinstance(expira_em, str):
        expira_em = datetime.fromisoformat(expira_em)
    agora = datetime.now(timezone.utc).replace(tzinfo=None) if expira_em.tzinfo is None else datetime.now(timezone.utc)
    expirou = agora > expira_em
    recebido = hashlib.sha256(codigo.strip().encode()).hexdigest()
    if tentativas >= 5 or expirou or not secrets.compare_digest(recebido, esperado):
        if tentativas >= 4 or expirou:
            conn.execute(f"UPDATE {tabela} SET usado = 1 WHERE id = ?", (codigo_id,))
        else:
            conn.execute(f"UPDATE {tabela} SET tentativas = tentativas + 1 WHERE id = ?", (codigo_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    conn.execute(f"UPDATE {tabela} SET usado = 1 WHERE id = ?", (codigo_id,))

inicializar_banco()

@app.get("/health")
def health():
    return {"status": "ok", "porta": 8001, "banco": "mysql", "versao": "2026.08.13-2"}

@app.get("/integracoes/status")
def status_integracoes():
    return diagnosticar_integracoes()

@app.post("/auth/login")
async def login(dados: LoginSchema):
    conn = conectar_banco()
    user = conn.execute("SELECT nome_completo, autorizado, tipo_usuario, senha_resetada, senha_hash FROM usuarios WHERE matricula = ?",
                        (dados.matricula.strip(),)).fetchone()
    conn.close()
    if not user or not pwd_context.verify(dados.senha, user[4]):
        raise HTTPException(status_code=401, detail="Matrícula ou senha incorretos.")
    if not user[1]:
        raise HTTPException(status_code=403, detail="Confirme o código enviado ao seu e-mail.")
    return {"msg": "Login realizado com sucesso!", "nome": user[0], "tipo_usuario": user[2],
            "precisa_mudar_senha": bool(user[3])}

@app.post("/auth/cadastrar")
async def cadastrar(dados: UserCreateSchema):
    email = dados.email.strip().lower()
    if not all((dados.matricula.strip(), dados.cpf.strip(), dados.nome_completo.strip(), email)):
        raise HTTPException(status_code=400, detail="Preencha todos os campos obrigatórios.")
    if not senha_e_forte(dados.senha):
        raise HTTPException(status_code=400, detail="Use 8 caracteres ou mais, com maiúscula, minúscula, número e símbolo.")
    conn = conectar_banco()
    try:
        existente = conn.execute(
            "SELECT id, autorizado, matricula, cpf FROM usuarios WHERE lower(email) = ?",
            (email,)
        ).fetchone()
        if existente and existente[1]:
            raise HTTPException(status_code=400, detail="Este e-mail já possui uma conta confirmada.")
        if existente:
            if existente[2] != dados.matricula.strip() or existente[3] != dados.cpf.strip():
                raise HTTPException(status_code=400, detail="Os dados não correspondem ao cadastro pendente.")
            conn.execute('''UPDATE usuarios SET nome_completo = ?, whatsapp = ?, data_nascimento = ?, senha_hash = ?
                WHERE id = ?''', (dados.nome_completo.strip(), dados.celular.strip(), dados.data_nascimento,
                                  gerar_hash(dados.senha), existente[0]))
        else:
            conn.execute('''INSERT INTO usuarios
                (matricula, cpf, nome_completo, email, whatsapp, data_nascimento, senha_hash, autorizado, tipo_usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'comum')''',
                (dados.matricula.strip(), dados.cpf.strip(), dados.nome_completo.strip(), email,
                 dados.celular.strip(), dados.data_nascimento, gerar_hash(dados.senha)))
        codigo = gerar_codigo()
        salvar_codigo(conn, "codigos_cadastro", email, codigo)
        enviar_codigo_email(email, codigo, "Confirme seu cadastro", "Seu código de confirmação é")
        conn.commit()
    except HTTPException:
        conn.rollback(); conn.close()
        raise
    except pymysql.IntegrityError:
        conn.rollback(); conn.close()
        raise HTTPException(status_code=400, detail="Matrícula, CPF ou e-mail já cadastrado.")
    except Exception as exc:
        conn.rollback(); conn.close()
        print(f"Erro ao enviar confirmação: {exc}")
        raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail. Tente novamente.")
    conn.close()
    return {"msg": "Código enviado para confirmar seu cadastro."}

@app.post("/auth/verificar-cadastro")
async def verificar_cadastro(dados: VerificacaoSchema):
    email = dados.email.strip().lower()
    conn = conectar_banco()
    validar_codigo(conn, "codigos_cadastro", email, dados.codigo)
    cursor = conn.execute("UPDATE usuarios SET autorizado = 1 WHERE lower(email) = ?", (email,))
    conn.commit(); conn.close()
    if not cursor.rowcount:
        raise HTTPException(status_code=400, detail="Cadastro não encontrado.")
    return {"msg": "Cadastro confirmado! Você já pode entrar."}

@app.post("/auth/esqueci-senha")
async def esqueci_senha(dados: EsqueciSenhaSchema):
    email = dados.email.strip().lower()
    conn = conectar_banco()
    existe = conn.execute("SELECT 1 FROM usuarios WHERE lower(email) = ? AND autorizado = 1", (email,)).fetchone()
    if not existe:
        conn.close()
        return {"msg": "Se o e-mail estiver cadastrado, o código será enviado."}
    codigo = gerar_codigo()
    try:
        salvar_codigo(conn, "recuperacoes_senha", email, codigo)
        enviar_codigo_email(email, codigo, "Recuperação de senha", "Seu código de recuperação é")
        conn.commit()
    except Exception as exc:
        conn.rollback(); conn.close()
        print(f"Erro ao enviar recuperação: {exc}")
        raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail. Tente novamente.")
    conn.close()
    return {"msg": "Se o e-mail estiver cadastrado, o código será enviado."}

@app.post("/auth/redefinir-senha")
async def redefinir_senha(dados: RedefinirSenhaSchema):
    if not senha_e_forte(dados.nova_senha):
        raise HTTPException(status_code=400, detail="Use 8 caracteres ou mais, com maiúscula, minúscula, número e símbolo.")
    email = dados.email.strip().lower()
    conn = conectar_banco()
    validar_codigo(conn, "recuperacoes_senha", email, dados.codigo)
    cursor = conn.execute("UPDATE usuarios SET senha_hash = ?, senha_resetada = 0 WHERE lower(email) = ?",
                          (gerar_hash(dados.nova_senha), email))
    conn.commit(); conn.close()
    if not cursor.rowcount:
        raise HTTPException(status_code=400, detail="Cadastro não encontrado.")
    return {"msg": "Senha redefinida com sucesso!"}

@app.post("/auth/definir-nova-senha")
async def definir_nova_senha(dados: NovaSenhaSchema):
    if not senha_e_forte(dados.nova_senha):
        raise HTTPException(status_code=400, detail="A nova senha não atende aos requisitos.")
    conn = conectar_banco()
    conn.execute("UPDATE usuarios SET senha_hash = ?, senha_resetada = 0 WHERE matricula = ?",
                 (gerar_hash(dados.nova_senha), dados.matricula.strip()))
    conn.commit(); conn.close()
    return {"msg": "Senha atualizada com sucesso!"}

@app.get("/admin/feriados")
async def listar_feriados():
    return verificar_feriados_nacionais()

@app.get("/consultar")
async def consultar_documento(documento: str = Query(...), tipo: str = Query("documento"),
                               exercicio: Optional[List[str]] = Query(None)):
    dados = buscar_dados_reais(documento, exercicio)
    return dados or {"nome": "Não Localizado", "documento": documento, "valor_divida": "0,00", "status": "Não Encontrado"}

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, tipo: Optional[str] = Query(None)):
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento")
    html = f"<html><body><h1>DADOS SMART</h1><p><b>Nome:</b> {dados.get('nome','N/A')}</p><p><b>Dívida:</b> R$ {dados.get('valor_divida','0,00')}</p></body></html>"
    caminho = os.path.join(BASE_DIR, f"relatorio_{documento}.pdf")
    executavel = os.getenv("WKHTMLTOPDF_PATH", r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
    pdfkit.from_string(html, caminho, configuration=pdfkit.configuration(wkhtmltopdf=executavel))
    return FileResponse(caminho, media_type="application/pdf", filename=os.path.basename(caminho))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
