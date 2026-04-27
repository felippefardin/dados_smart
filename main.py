from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Optional
import pdfkit
import os
from datetime import datetime
from integracao import buscar_dados_reais
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse

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
    exercicio: Optional[List[str]] = Query(None) # Permite múltiplos como ?exercicio=2023&exercicio=2024
):
    # Passa a lista de exercícios para a integração
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

@app.get("/gerar-excel/{documento}")
async def gerar_excel_rota(
    documento: str, 
    tipo: Optional[str] = Query(None), # Adicionado para capturar o ?tipo= enviado pelo JS
    exercicio: Optional[List[str]] = Query(None)
):
    # Chamada correta da função interna
    dados = await consultar_documento(documento=documento, tipo=tipo, exercicio=exercicio)
    
    # Se 'dados' for um único dicionário, transformamos em lista para o DataFrame
    lista_dados = [dados] if isinstance(dados, dict) else dados
    
    # Cria o DataFrame do Pandas
    df = pd.DataFrame(lista_dados)
    
    # Renomeia as colunas para um formato amigável
    colunas_map = {
        "nome": "Nome/Razão Social",
        "documento": "CPF/CNPJ",
        "exercicio": "Exercícios",
        "valor_divida": "Valor da Dívida (R$)",
        "status": "Situação",
        "estornado": "Estornado",
        "endereco": "Endereço Completo"
    }
    
    # Filtra apenas as colunas que existem no dicionário para evitar erro de renomeação
    df = df.rename(columns={k: v for k, v in colunas_map.items() if k in df.columns})

    # Cria o arquivo Excel em memória
    output = BytesIO()
    # Certifique-se de ter instalado: pip install openpyxl
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
    
    output.seek(0)

    filename = f"relatorio_{documento}.xlsx"
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/gerar-pdf/{documento}")
async def gerar_pdf_rota(documento: str, exercicio: Optional[List[str]] = Query(None)):
    dados = await consultar_documento(documento, "documento", exercicio)
    
    html_template = f"""
    <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="text-align: center;">DADOS SMART</h1>
            <h2 style="text-align: center;">Relatório de Débitos Consolidados</h2>
            <hr>
            <p><strong>Nome:</strong> {dados.get('nome')}</p>
            <p><strong>Documento:</strong> {dados.get('documento')}</p>
            <p><strong>Exercícios Consultados:</strong> {dados.get('exercicio')}</p>
            <p><strong>Valor Total:</strong> R$ {dados.get('valor_divida')}</p>
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
    except Exception as e:
        print(f"Erro PDF: {e}")
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

    