import requests
from datetime import datetime

# Token da API CPFHub
API_TOKEN_CPFHUB = "2e8d63a30a8aa06092b6fad5bc02d7d4a9782bc704d578f9433635022b5119e6"

def consultar_divida_ativa_federal(doc_limpo):
    """
    Consulta débitos na Dívida Ativa da União via API de Dados Abertos da PGFN.
    Retorna o valor total formatado e os exercícios encontrados.
    """
    url = f"https://dadosabertos.pgfn.gov.br/api/v1/devedores/{doc_limpo}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            dados = response.json()
            debitos = dados.get("debitos", [])
            
            if not debitos:
                return "0,00", "N/A"
            
            # Extrai os anos (exercícios) únicos das inscrições
            anos_encontrados = set()
            valor_total = 0.0
            
            for d in debitos:
                valor_total += d.get("valor_consolidado", 0.0)
                # Tenta capturar o ano da data de inscrição (formato esperado: YYYY-MM-DD)
                data_insc = d.get("data_inscricao")
                if data_insc and "-" in data_insc:
                    anos_encontrados.add(data_insc.split("-")[0])
            
            # Formata exercícios como string (ex: "2021, 2022")
            exercicios_reais = ", ".join(sorted(anos_encontrados)) if anos_encontrados else "Não informado"
            
            # Formata o valor total como moeda brasileira
            valor_formatado = f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            return valor_formatado, exercicios_reais
            
        return "0,00", "N/A"
    except Exception as e:
        print(f"Erro PGFN: {e}")
        return "0,00", "Erro na API"

def buscar_dados_reais(documento, exercicios=None):
    """
    Busca dados de CNPJ (BrasilAPI) ou CPF (CPFHub) e formata para o sistema.
    """
    if not exercicios:
        exercicios = [str(datetime.now().year)]
    
    exercicios_default = ", ".join(exercicios)
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    if len(doc_limpo) == 14: # Lógica para CNPJ
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                dados_api = response.json()
                
                logradouro = dados_api.get("logradouro", "N/A")
                numero = dados_api.get("numero", "S/N")
                bairro = dados_api.get("bairro", "N/A")
                cep = dados_api.get("cep", "N/A")
                municipio = dados_api.get("municipio", "N/A")
                uf = dados_api.get("uf", "N/A")
                endereco_completo = f"{logradouro}, nº {numero}, {bairro} - {municipio}/{uf}, CEP: {cep}"
                
                # Busca valores e exercícios reais na PGFN
                valor_real, anos_reais = consultar_divida_ativa_federal(doc_limpo)
                
                return {
                    "nome": dados_api.get("razao_social", "Nada Consta"),
                    "documento": documento,
                    "data_nascimento": "N/A (PJ)",
                    "exercicio": anos_reais if anos_reais != "N/A" else exercicios_default,
                    "endereco": endereco_completo,
                    "status": dados_api.get("descricao_situacao_cadastral", "ATIVA"),
                    "valor_divida": valor_real,
                    "estornado": "Não"
                }
        except Exception as e:
            print(f"Erro CNPJ: {e}")

    elif len(doc_limpo) == 11: # Lógica para CPF
        url = f"https://api.cpfhub.io/cpf/{doc_limpo}"
        headers = {'x-api-key': API_TOKEN_CPFHUB, 'Accept': 'application/json'}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                resposta = response.json()
                if resposta.get("success"):
                    dados = resposta.get("data", {})
                    data_nasc = dados.get("birthDate") or dados.get("birth_date") or "N/A"
                    
                    addr = dados.get("address", {})
                    if addr:
                        end_cpf = f"{addr.get('street', 'N/A')}, {addr.get('number', 'S/N')} - {addr.get('city', 'N/A')}/{addr.get('state', 'N/A')}"
                    else:
                        end_cpf = "Endereço indisponível no plano/API"

                    # Busca valores e exercícios reais na PGFN
                    valor_real, anos_reais = consultar_divida_ativa_federal(doc_limpo)

                    return {
                        "nome": dados.get("name", "N/A"),
                        "documento": documento,
                        "data_nascimento": data_nasc,
                        "exercicio": anos_reais if anos_reais != "N/A" else exercicios_default,
                        "endereco": end_cpf,
                        "status": "REGULAR",
                        "valor_divida": valor_real,
                        "estornado": "Não"
                    }
        except Exception as e:
            print(f"Erro CPF: {e}")
    
    return None