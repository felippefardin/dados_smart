import requests
from datetime import datetime

# Sua chave de API do CPFhub.io (conforme documentação de 2026)
API_TOKEN_CPFHUB = "2e8d63a30a8aa06092b6fad5bc02d7d4a9782bc704d578f9433635022b5119e6"

def buscar_dados_reais(documento):
    # Obtém o ano atual dinamicamente
    ano_atual = str(datetime.now().year)
    
    # Remove qualquer caractere que não seja número
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    # --- LÓGICA PARA CNPJ (14 dígitos) via BrasilAPI ---
    if len(doc_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                dados_api = response.json()
                return {
                    "nome": dados_api.get("razao_social", "Nada Consta"),
                    "documento": documento,
                    "data_nascimento": "N/A (Empresa)",
                    "exercicio": ano_atual, # Ano dinâmico aplicado aqui
                    "valor_divida": "0,00", 
                    "status": dados_api.get("descricao_situacao_cadastral", "Nada Consta"),
                    "estornado": "Não",
                    "endereco": f"{dados_api.get('municipio', 'Nada Consta')}, {dados_api.get('uf', 'Nada Consta')}"
                }
        except Exception as e:
            print(f"Erro na conexão com a API CNPJ: {e}")

    # --- LÓGICA PARA CPF (11 dígitos) via CPFHub.io ---
    elif len(doc_limpo) == 11:
        url = f"https://api.cpfhub.io/cpf/{doc_limpo}" 
        headers = {
            'x-api-key': API_TOKEN_CPFHUB,
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                resposta = response.json()
                if resposta.get("success"):
                    dados = resposta.get("data", {})
                    return {
                        "nome": dados.get("name", "Nome não disponível"),
                        "documento": documento,
                        "data_nascimento": dados.get("birthDate", "N/A"),
                        "exercicio": ano_atual, # Ano dinâmico aplicado aqui
                        "valor_divida": "0,00",
                        "status": "REGULAR",
                        "estornado": "Não",
                        "endereco": "Consulta via CPFhub"
                    }
            elif response.status_code == 401:
                print("Erro: Chave de API inválida.")
        except Exception as e:
            print(f"Erro na conexão com a API CPFhub: {e}")
    
    return None