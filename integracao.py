import requests
from datetime import datetime

API_TOKEN_CPFHUB = "2e8d63a30a8aa06092b6fad5bc02d7d4a9782bc704d578f9433635022b5119e6"

def buscar_dados_reais(documento, exercicios=None):
    if not exercicios:
        exercicios = [str(datetime.now().year)]
    
    exercicios_str = ", ".join(exercicios)
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    if len(doc_limpo) == 14: # CNPJ via BrasilAPI
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                dados_api = response.json()
                
                # Mapeamento detalhado para evitar o "bloqueio" visual
                logradouro = dados_api.get("logradouro", "N/A")
                numero = dados_api.get("numero", "S/N")
                bairro = dados_api.get("bairro", "N/A")
                cep = dados_api.get("cep", "N/A")
                municipio = dados_api.get("municipio", "N/A")
                uf = dados_api.get("uf", "N/A")
                
                endereco_completo = f"{logradouro}, nº {numero}, {bairro} - {municipio}/{uf}, CEP: {cep}"
                
                return {
                    "nome": dados_api.get("razao_social", "Nada Consta"),
                    "documento": documento,
                    "exercicio": exercicios_str,
                    "endereco": endereco_completo,
                    "status": dados_api.get("descricao_situacao_cadastral", "ATIVA"),
                    "valor_divida": "0,00",
                    "estornado": "Não"
                }
        except Exception as e:
            print(f"Erro CNPJ: {e}")

    elif len(doc_limpo) == 11: # CPF via CPFHub
        url = f"https://api.cpfhub.io/cpf/{doc_limpo}"
        headers = {'x-api-key': API_TOKEN_CPFHUB, 'Accept': 'application/json'}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                resposta = response.json()
                if resposta.get("success"):
                    dados = resposta.get("data", {})
                    # Tenta buscar o objeto de endereço (verificar se seu plano permite)
                    addr = dados.get("address", {})
                    if addr:
                        end_cpf = f"{addr.get('street')}, {addr.get('number')} - {addr.get('city')}/{addr.get('state')}"
                    else:
                        end_cpf = "Endereço não retornado pela API (Privacidade/Plano)"

                    return {
                        "nome": dados.get("name", "N/A"),
                        "documento": documento,
                        "exercicio": exercicios_str,
                        "endereco": end_cpf,
                        "status": "REGULAR",
                        "valor_divida": "0,00",
                        "estornado": "Não"
                    }
        except Exception as e:
            print(f"Erro CPF: {e}")
    
    return None