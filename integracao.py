import os
import re
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _sessao_http():
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        status=3,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
        respect_retry_after_header=True,
    )
    sessao = requests.Session()
    sessao.headers.update({"Accept": "application/json", "User-Agent": "DadosSmart/1.0"})
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


HTTP = _sessao_http()


def _somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def consultar_cep(cep):
    cep_limpo = _somente_digitos(cep)
    if len(cep_limpo) != 8:
        return None
    try:
        resposta = HTTP.get(f"https://brasilapi.com.br/api/cep/v1/{cep_limpo}", timeout=(5, 15))
        if resposta.status_code == 200:
            return resposta.json()
    except requests.RequestException as exc:
        print(f"BrasilAPI CEP indisponível: {exc}")
    return None


def verificar_feriados_nacionais(ano=None):
    ano_consulta = int(ano or datetime.now().year)
    if ano_consulta < 1900 or ano_consulta > 2199:
        return []
    try:
        resposta = HTTP.get(f"https://brasilapi.com.br/api/feriados/v1/{ano_consulta}", timeout=(5, 15))
        if resposta.status_code == 200:
            dados = resposta.json()
            return dados if isinstance(dados, list) else []
    except requests.RequestException as exc:
        print(f"BrasilAPI Feriados indisponível: {exc}")
    return []


def _endereco(partes):
    logradouro = partes.get("logradouro") or partes.get("street") or "Não informado"
    numero = partes.get("numero") or partes.get("number") or "S/N"
    bairro = partes.get("bairro") or partes.get("neighborhood") or ""
    cidade = partes.get("municipio") or partes.get("city") or ""
    uf = partes.get("uf") or partes.get("state") or ""
    linha = f"{logradouro}, {numero}"
    if bairro:
        linha += f" - {bairro}"
    if cidade or uf:
        linha += f" - {cidade}/{uf}".rstrip("/")
    return linha


def _consultar_cnpj_brasilapi(cnpj):
    resposta = HTTP.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", timeout=(5, 20))
    if resposta.status_code != 200:
        return None
    dados = resposta.json()
    return {
        "nome": dados.get("razao_social") or dados.get("nome_fantasia") or "Não informado",
        "endereco": _endereco(dados),
        "status": dados.get("descricao_situacao_cadastral") or "Não informado",
        "fonte_cadastro": "BrasilAPI",
    }


def _consultar_cnpj_opencnpj(cnpj):
    resposta = HTTP.get(f"https://kitana.opencnpj.com/cnpj/{cnpj}", timeout=(5, 20))
    if resposta.status_code != 200:
        return None
    corpo = resposta.json()
    dados = corpo.get("data") if isinstance(corpo, dict) else None
    if not corpo.get("success") or not isinstance(dados, dict):
        return None
    return {
        "nome": dados.get("razaoSocial") or dados.get("nomeFantasia") or "Não informado",
        "endereco": _endereco(dados),
        "status": dados.get("situacaoCadastral") or "Não informado",
        "fonte_cadastro": "OpenCNPJ",
    }


def _consultar_cpf(cpf):
    chave = os.getenv("API_TOKEN_CPFHUB", "").strip()
    if not chave:
        raise RuntimeError("API_TOKEN_CPFHUB não configurado")
    resposta = HTTP.get(
        f"https://api.cpfhub.io/cpf/{cpf}",
        headers={"x-api-key": chave},
        timeout=(5, 20),
    )
    if resposta.status_code != 200:
        try:
            erro = resposta.json().get("error", {})
            print(f"CPFHub {resposta.status_code}: {erro.get('code')} - {erro.get('message')}")
        except ValueError:
            print(f"CPFHub retornou HTTP {resposta.status_code}")
        return None
    corpo = resposta.json()
    dados = corpo.get("data", {})
    if not corpo.get("success") or not isinstance(dados, dict):
        return None
    return {
        "nome": dados.get("name") or "Não informado",
        "data_nascimento": dados.get("birthDate") or "Não informado",
        "endereco": "Não fornecido pela CPFHub",
        "status": "CPF localizado",
        "fonte_cadastro": "CPFHub",
    }


def buscar_dados_reais(documento, exercicios=None):
    doc_limpo = _somente_digitos(documento)
    exercicio = ", ".join(exercicios or [str(datetime.now().year)])
    cadastro = None

    try:
        if len(doc_limpo) == 14:
            try:
                cadastro = _consultar_cnpj_brasilapi(doc_limpo)
            except requests.RequestException as exc:
                print(f"BrasilAPI CNPJ indisponível: {exc}")
            if not cadastro:
                try:
                    cadastro = _consultar_cnpj_opencnpj(doc_limpo)
                except requests.RequestException as exc:
                    print(f"OpenCNPJ indisponível: {exc}")
            data_nascimento = "N/A (pessoa jurídica)"
        elif len(doc_limpo) == 11:
            cadastro = _consultar_cpf(doc_limpo)
            data_nascimento = cadastro.get("data_nascimento") if cadastro else "Não informado"
        else:
            return None
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        print(f"Falha na integração cadastral: {exc}")
        return None

    if not cadastro:
        return None
    return {
        "nome": cadastro["nome"],
        "documento": doc_limpo,
        "data_nascimento": data_nascimento,
        "exercicio": exercicio,
        "endereco": cadastro["endereco"],
        "status": cadastro["status"],
        "valor_divida": "Não disponível",
        "estornado": "Não informado",
        "fonte_cadastro": cadastro["fonte_cadastro"],
        "observacao_divida": "A PGFN não oferece o endpoint individual que o sistema utilizava anteriormente.",
    }


def diagnosticar_integracoes():
    resultado = {}
    testes = {
        "brasilapi_cep": ("https://brasilapi.com.br/api/cep/v1/01001000", {}),
        "brasilapi_feriados": (f"https://brasilapi.com.br/api/feriados/v1/{datetime.now().year}", {}),
        "opencnpj": ("https://kitana.opencnpj.com/cnpj/00000000000191", {}),
    }
    for nome, (url, headers) in testes.items():
        try:
            resposta = HTTP.get(url, headers=headers, timeout=(5, 15))
            resultado[nome] = {"ok": resposta.status_code == 200, "http": resposta.status_code}
        except requests.RequestException as exc:
            resultado[nome] = {"ok": False, "erro": type(exc).__name__}
    resultado["cpfhub_configurada"] = {"ok": bool(os.getenv("API_TOKEN_CPFHUB", "").strip())}
    resultado["pgfn"] = {"ok": False, "motivo": "endpoint individual anterior inexistente"}
    return resultado
