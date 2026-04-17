from integracao import buscar_dados_reais
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional
import sqlite3
import pdfkit
from jinja2 import Template
import os

app = FastAPI(title="Dados Smart - Integrador")

# Configuração de CORS para permitir acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulação de base de dados (Fallback)
def mock_api_externa(documento: str):
    doc_limpo = documento.replace(".", "").replace("-", "").replace("/", "")
    base_dados = {
        "nome": "Felippe Fardin" if len(doc_limpo) <= 11 else "Fardin Tecnologia LTDA",
        "documento": documento,
        "valor_divida": 2500.00 if len(doc_limpo) <= 11 else 15400.00,
        "data_vencimento": "2026-05-20",
        "status": "Em Aberto",
        "tipo_pessoa": "Física" if len(doc_limpo) <= 11 else "Jurídica",
        "endereco": "Serra, ES"
    }
    return base_dados

@app.get("/gerar-relatorio")
async def gerar_relatorio(documento: str, campos_selecionados: Optional[str] = Query(None)):
    # 1. Tenta buscar primeiro na API REAL (integracao.py)
    dados_brutos = buscar_dados_reais(documento)
    
    # 2. Se a integração retornar None ou falhar, usa o Mock
    if dados_brutos is None:
        dados_brutos = mock_api_externa(documento)

    # Registro de log no banco de dados SQLite
    try:
        conn = sqlite3.connect('dados_smart.db')
        conn.execute("INSERT INTO logs_consulta (usuario, cpf_consultado) VALUES (?, ?)", ("Admin", documento))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar log: {e}")

    # Filtra os campos conforme a seleção do usuário no index.html
    if campos_selecionados:
        lista_campos = campos_selecionados.split(",")
        return {k: v for k, v in dados_brutos.items() if k in lista_campos}
    
    return dados_brutos

@app.get("/gerar-pdf")
async def gerar_pdf(documento: str, campos_selecionados: Optional[str] = Query(None)):
    # 1. Tenta buscar dados reais para compor o PDF
    dados_brutos = buscar_dados_reais(documento)
    
    # 2. Fallback para o Mock se necessário
    if dados_brutos is None:
        dados_brutos = mock_api_externa(documento)
    
    if campos_selecionados:
        lista_campos = campos_selecionados.split(",")
        dados = {k: v for k, v in dados_brutos.items() if k in lista_campos}
    else:
        dados = dados_brutos

    # Template HTML para o motor do PDF
    html_template = """
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'Helvetica', sans-serif; color: #333; margin: 40px; }
            .header { text-align: center; border-bottom: 3px solid #0056b3; padding-bottom: 10px; margin-bottom: 30px; }
            h1 { color: #0056b3; font-size: 28px; margin-bottom: 5px; }
            .info { margin-bottom: 20px; font-size: 14px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { background-color: #0056b3; color: white; padding: 12px; text-align: left; text-transform: uppercase; font-size: 12px; }
            td { border: 1px solid #ddd; padding: 12px; font-size: 13px; }
            .footer { margin-top: 50px; text-align: center; font-size: 10px; color: #777; border-top: 1px solid #eee; padding-top: 10px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>DADOS SMART</h1>
            <p>Relatório Consolidado de Débitos</p>
        </div>
        <div class="info">
            <strong>Documento Consultado:</strong> {{ documento }} <br>
            <strong>Data de Emissão:</strong> 17/04/2026
        </div>
        <table>
            <thead>
                <tr>
                    {% for chave in dados.keys() %}
                        <th>{{ chave.replace('_', ' ') }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                <tr>
                    {% for valor in dados.values() %}
                        <td>{{ valor }}</td>
                    {% endfor %}
                </tr>
            </tbody>
        </table>
        <div class="footer">
            Este documento é uma consulta direta ao sistema integrador Dados Smart. <br>
            A autenticidade deste relatório pode ser verificada internamente.
        </div>
    </body>
    </html>
    """
    
    template = Template(html_template)
    html_final = template.render(dados=dados, documento=documento)

    # Caminho do executável wkhtmltopdf
    path_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    if not os.path.exists(path_wk):
        raise HTTPException(status_code=500, detail="Motor PDF não encontrado no servidor.")

    try:
        config = pdfkit.configuration(wkhtmltopdf=path_wk)
        pdf_nome = f"relatorio_{documento}.pdf"
        
        # Gera e retorna o arquivo PDF
        pdfkit.from_string(html_final, pdf_nome, configuration=config)
        return FileResponse(pdf_nome, media_type='application/pdf', filename=pdf_nome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # reload=True ajuda a reiniciar o servidor automaticamente ao salvar arquivos
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)