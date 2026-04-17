import requests

def buscar_dados_reais(documento):
    # Limpa o documento para a URL
    doc_limpo = documento.replace(".", "").replace("-", "").replace("/", "")
    
    # A BrasilAPI é excelente para testar CNPJ (mais de 11 dígitos)
    if len(doc_limpo) > 11:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
    else:
        # Para CPF, mantemos None para que o sistema use o Mock (simulação)
        return None

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados_api = response.json()
            # Mapeia os campos e define "Nada Consta" para os que a API não possui
            return {
                "nome": dados_api.get("razao_social", "Nada Consta"),
                "documento": documento,
                "valor_divida": "Nada Consta", # Campo não disponível na API gratuita
                "data_vencimento": "Nada Consta", # Campo não disponível na API gratuita
                "status": dados_api.get("descricao_situacao_cadastral", "Nada Consta"),
                "tipo_pessoa": "Jurídica",
                "endereco": f"{dados_api.get('municipio', 'Nada Consta')}, {dados_api.get('uf', 'Nada Consta')}"
            }
    except Exception as e:
        print(f"Erro na conexão com a API: {e}")
    
    return None