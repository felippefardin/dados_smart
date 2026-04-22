import requests

def buscar_dados_reais(documento):
    # Garante que apenas números sejam enviados, removendo espaços, pontos ou traços
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    # BrasilAPI exige 14 dígitos para CNPJ
    if len(doc_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
    else:
        return None

    try:
        response = requests.get(url, timeout=15) # Aumentado o timeout para conexões lentas
        if response.status_code == 200:
            dados_api = response.json()
            return {
                "nome": dados_api.get("razao_social", "Nada Consta"),
                "documento": documento,
                "exercicio": "2024", 
                "valor_divida": "0,00", 
                "status": dados_api.get("descricao_situacao_cadastral", "Nada Consta"),
                "estornado": "Não",
                "endereco": f"{dados_api.get('municipio', 'Nada Consta')}, {dados_api.get('uf', 'Nada Consta')}"
            }
        else:
            print(f"API retornou erro {response.status_code} para o documento {doc_limpo}")
    except Exception as e:
        print(f"Erro na conexão com a API: {e}")
    
    return None