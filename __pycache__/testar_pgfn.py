from integracao import consultar_divida_ativa_federal

# Teste com um CNPJ que sabidamente possui dívida ativa (Ex: JBS - 39.775.783/0001-10)
# Ou use um documento que você saiba que está na base da PGFN
doc_teste = "39775783000110" 

print(f"Consultando débitos para: {doc_teste}...")
resultado = consultar_divida_ativa_federal(doc_teste)
print(f"Resultado retornado: R$ {resultado}")