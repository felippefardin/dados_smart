from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pdfkit
from datetime import datetime
from integracao import buscar_dados_reais

app = FastAPI(title="Dados Smart - Integrador")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/consultar")
async def consultar_documento(documento: str = Query(...), tipo: str = Query("documento")):
    # Tenta buscar os dados reais primeiro
    dados = buscar_dados_reais(documento)
    
    if dados:
        return dados

    # Se não encontrar na API, retorna o objeto com status informativo
    return {
        "nome": "Não Localizado",
        "documento": documento,
        "exercicio": "N/A",
        "valor_divida": "0,00",
        "status": "Não Encontrado na API",
        "estornado": "N/A",
        "endereco": "N/A"
    }

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, tipo: str = Query("documento")):
    dados = await consultar_documento(documento, tipo)
    
    html_template = f"""
    <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="text-align: center;">DADOS SMART</h1>
            <h2 style="text-align: center;">Relatório de Débitos Consolidados</h2>
            <hr>
            <p><strong>Nome:</strong> {dados.get('nome')}</p>
            <p><strong>Documento:</strong> {dados.get('documento')}</p>
            <p><strong>Exercício:</strong> {dados.get('exercicio')}</p>
            <p><strong>Valor:</strong> R$ {dados.get('valor_divida')}</p>
            <p><strong>Status:</strong> {dados.get('status')}</p>
            <p><strong>Estornado:</strong> {dados.get('estornado')}</p>
            <p><strong>Endereço:</strong> {dados.get('endereco')}</p>
            <br>
            <footer style="text-align: center; font-size: 10px;">
                Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </footer>
        </body>
    </html>
    """
    path_pdf = f"relatorio_{documento}.pdf"
    try:
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdfkit.from_string(html_template, path_pdf, configuration=config)
        return FileResponse(path_pdf, media_type='application/pdf', filename=path_pdf)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF.")