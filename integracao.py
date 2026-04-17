# import requests
# import os

# def buscar_dados_reais(cpf):
#     # Quando tiver a API, você usará as variáveis do .env
#     url = "https://api.sistema-origem.com/v1/dados"
#     token = os.getenv("API_TOKEN") 
    
#     # response = requests.get(f"{url}/{cpf}", headers={"Authorization": f"Bearer {token}"})
#     # return response.json()
#     pass


import requests

def buscar_dados_reais(documento):
    # Limpa o documento para a URL
    doc_limpo = documento.replace(".", "").replace("-", "").replace("/", "")
    
    # A BrasilAPI é excelente para testar CNPJ (mais de 11 dígitos)
    if len(doc_limpo) > 11:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
    else:
        # Para CPF, como é dado sensível, manteremos o seu Mock por enquanto
        return None 

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados_api = response.json()
            # Mapeia os campos da API externa para o formato que seu sistema espera
            return {
                "nome": dados_api.get("razao_social"),
                "documento": documento,
                "valor_divida": 0.0,  # Valor fictício pois a API é cadastral
                "status": dados_api.get("descricao_situacao_cadastral"),
                "tipo_pessoa": "Jurídica",
                "endereco": f"{dados_api.get('municipio')}, {dados_api.get('uf')}"
            }
    except Exception as e:
        print(f"Erro na conexão com a API: {e}")
    
    return None