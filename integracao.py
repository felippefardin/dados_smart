import requests

def buscar_dados_reais(documento):
    # Remove qualquer caractere que não seja número (espaços, pontos, traços)
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    # A BrasilAPI requer exatamente 14 dígitos para busca de CNPJ
    if len(doc_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
    else:
        # Se for CPF ou outro formato, a integração atual retorna None
        return None

    try:
        # Chamada real para a API externa
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            dados_api = response.json()
            # Mapeia os campos da BrasilAPI para o formato do seu sistema
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