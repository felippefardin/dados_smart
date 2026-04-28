import requests
from datetime import datetime

# Token da API CPFHub
API_TOKEN_CPFHUB = "2e8d63a30a8aa06092b6fad5bc02d7d4a9782bc704d578f9433635022b5119e6"

def consultar_divida_ativa_federal(doc_limpo):
    """
    Consulta débitos na Dívida Ativa da União via API de Dados Abertos da PGFN.
    Retorna o valor total formatado e os anos (exercícios) encontrados.
    """
    url = f"https://dadosabertos.pgfn.gov.br/api/v1/devedores/{doc_limpo}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            debitos = dados.get("debitos", [])
            
            if not debitos:
                return "0,00", None
            
            valor_total = 0.0
            anos = set()
            
            for d in debitos:
                valor_total += d.get("valor_consolidado", 0.0)
                data_insc = d.get("data_inscricao")
                if data_insc and "-" in data_insc:
                    anos.add(data_insc.split("-")[0])
            
            # Formatação Brasileira (R$ 1.234,56)
            valor_formatado = f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            exercicios_reais = ", ".join(sorted(anos)) if anos else None
            
            return valor_formatado, exercicios_reais
        return "0,00", None
    except Exception as e:
        print(f"Erro PGFN (Dívida Federal): {e}")
        return "0,00", None

def buscar_dados_reais(documento, exercicios=None):
    """
    Busca dados de CNPJ (BrasilAPI/OpenCNPJ) ou CPF (CPFHub) e integra com PGFN.
    """
    if not exercicios:
        exercicios = [str(datetime.now().year)]
    
    exercicios_default = ", ".join(exercicios)
    doc_limpo = "".join(filter(str.isdigit, documento))
    
    # BUSCA DE VALOR E EXERCÍCIOS REAIS NA PGFN (Dívida Ativa da União)
    valor_pgfn, anos_pgfn = consultar_divida_ativa_federal(doc_limpo)
    exercicio_final = anos_pgfn if anos_pgfn else exercicios_default

    # --- LÓGICA PARA CNPJ (PESSOA JURÍDICA) ---
    if len(doc_limpo) == 14:
        # Tenta BrasilAPI primeiro
        url = f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                d = res.json()
                endereco = f"{d.get('logradouro')}, {d.get('numero')}, {d.get('bairro')} - {d.get('municipio')}/{d.get('uf')}"
                return {
                    "nome": d.get("razao_social"),
                    "documento": documento,
                    "data_nascimento": "N/A (PJ)",
                    "exercicio": exercicio_final,
                    "endereco": endereco,
                    "status": d.get("descricao_situacao_cadastral", "ATIVA"),
                    "valor_divida": valor_pgfn,
                    "estornado": "Não"
                }
            
            # BACKUP: OpenCNPJ (Caso BrasilAPI falhe)
            url_backup = f"https://kitana.opencnpj.com/cnpj/{doc_limpo}"
            res_b = requests.get(url_backup, timeout=10)
            if res_b.status_code == 200:
                d = res_b.json()
                return {
                    "nome": d.get("razao_social"),
                    "documento": documento,
                    "data_nascimento": "N/A (PJ)",
                    "exercicio": exercicio_final,
                    "endereco": f"{d.get('logradouro')}, {d.get('bairro')} - {d.get('municipio')}/{d.get('uf')}",
                    "status": "ATIVA",
                    "valor_divida": valor_pgfn,
                    "estornado": "Não"
                }
        except Exception as e:
            print(f"Erro em APIs de CNPJ: {e}")

    # --- LÓGICA PARA CPF (PESSOA FÍSICA) ---
    elif len(doc_limpo) == 11:
        url = f"https://api.cpfhub.io/cpf/{doc_limpo}"
        headers = {'x-api-key': API_TOKEN_CPFHUB, 'Accept': 'application/json'}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                resposta = res.json()
                if resposta.get("success"):
                    d = resposta.get("data", {})
                    data_nasc = d.get("birthDate") or d.get("birth_date") or "N/A"
                    addr = d.get("address", {})
                    end_str = f"{addr.get('street', 'N/A')}, {addr.get('number', 'S/N')} - {addr.get('city', 'N/A')}/{addr.get('state', 'N/A')}" if addr else "Não informado"

                    return {
                        "nome": d.get("name", "N/A"),
                        "documento": documento,
                        "data_nascimento": data_nasc,
                        "exercicio": exercicio_final,
                        "endereco": end_str,
                        "status": "REGULAR",
                        "valor_divida": valor_pgfn,
                        "estornado": "Não"
                    }
        except Exception as e:
            print(f"Erro CPFHub: {e}")
    
    return None