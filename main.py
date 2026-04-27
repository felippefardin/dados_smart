from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
import pdfkit
import os
import pandas as pd
from io import BytesIO
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
        "exercicio": ", ".join(exercicio) if exercicio else "N/A",
        "valor_divida": "0,00",
        "status": "Não Encontrado na API",
        "estornado": "N/A",
        "endereco": "N/A"
    }

# ROTA CORRIGIDA PARA EXCEL
@app.get("/gerar-excel/{documento}")
async def gerar_excel_rota(
    documento: str, 
    tipo: Optional[str] = Query(None), 
    exercicio: Optional[List[str]] = Query(None)
):
    # Forçamos o await para garantir a obtenção dos dados
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento", exercicio=exercicio)
    
    df = pd.DataFrame([dados])
    
    colunas_map = {
        "nome": "Nome/Razão Social",
        "documento": "CPF/CNPJ",
        "exercicio": "Exercícios",
        "valor_divida": "Valor da Dívida (R$)",
        "status": "Situação",
        "estornado": "Estornado",
        "endereco": "Endereço Completo"
    }
    df = df.rename(columns={k: v for k, v in colunas_map.items() if k in df.columns})

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
    
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{documento}.xlsx"}
    )

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, exercicio: Optional[List[str]] = Query(None)):
    dados = await consultar_documento(documento, "documento", exercicio)
    html_template = f"<html><body><h1>DADOS SMART</h1><p>Nome: {dados.get('nome')}</p></body></html>"
    path_pdf = f"relatorio_{documento}.pdf"
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    pdfkit.from_string(html_template, path_pdf, configuration=config)
    return FileResponse(path_pdf, media_type='application/pdf', filename=path_pdf)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)