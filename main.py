from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import pdfkit
import os
import pandas as pd
from io import BytesIO
from datetime import datetime

# Importação da sua lógica de busca
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
    # 1. Busca os dados reais (igual ao PDF)
    dados = await consultar_documento(documento=documento, tipo=tipo or "documento", exercicio=exercicio)
    
    # 2. Transforma em DataFrame do Pandas
    df = pd.DataFrame([dados])
    
    # 3. Mapeia os nomes das colunas para ficarem amigáveis no Excel
    colunas_map = {
        "nome": "Nome/Razão Social",
        "documento": "CPF/CNPJ",
        "data_nascimento": "Data de Nascimento",
        "exercicio": "Exercícios",
        "valor_divida": "Valor da Dívida (R$)",
        "status": "Situação/Status",
        "estornado": "Estornado",
        "endereco": "Endereço Completo"
    }
    
    # Renomeia apenas as colunas que existem no resultado
    df = df.rename(columns={k: v for k, v in colunas_map.items() if k in df.columns})

    # 4. Gera o arquivo em memória
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