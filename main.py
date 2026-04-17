from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional
import sqlite3
import pdfkit
from jinja2 import Template
import os

app = FastAPI(title="Dados Smart - Integrador")

# Configuração de CORS para permitir que o seu index.html acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulação de base de dados externa
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
    dados_brutos = mock_api_externa(documento)
    try:
        conn = sqlite3.connect('dados_smart.db')
        conn.execute("INSERT INTO logs_consulta (usuario, cpf_consultado) VALUES (?, ?)", ("Admin", documento))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar log: {e}")

    if campos_selecionados:
        lista_campos = campos_selecionados.split(",")
        return {k: v for k, v in dados_brutos.items() if k in lista_campos}
    return dados_brutos

@app.get("/gerar-pdf")
async def gerar_pdf(documento: str, campos_selecionados: Optional[str] = Query(None)):
    dados_brutos = mock_api_externa(documento)
    
    if campos_selecionados:
        lista_campos = campos_selecionados.split(",")
        dados = {k: v for k, v in dados_brutos.items() if k in lista_campos}
    else:
        dados = dados_brutos

    # Template HTML para o PDF
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
            <strong>Data de Emissão:</strong> 16/04/2026
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

    # CAMINHO CORRIGIDO: Apontando para o executável dentro da pasta bin
    path_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    # Verificação de segurança para te ajudar a debugar
    if not os.path.exists(path_wk):
        raise HTTPException(status_code=500, detail=f"Motor PDF não encontrado em: {path_wk}. Verifique a instalação.")

    try:
        config = pdfkit.configuration(wkhtmltopdf=path_wk)
        pdf_nome = f"relatorio_{documento}.pdf"
        
        # Gera o PDF
        pdfkit.from_string(html_final, pdf_nome, configuration=config)
        
        # Retorna o arquivo
        return FileResponse(pdf_nome, media_type='application/pdf', filename=pdf_nome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)