import requests
import os

def buscar_dados_reais(cpf):
    # Quando tiver a API, você usará as variáveis do .env
    url = "https://api.sistema-origem.com/v1/dados"
    token = os.getenv("API_TOKEN") 
    
    # response = requests.get(f"{url}/{cpf}", headers={"Authorization": f"Bearer {token}"})
    # return response.json()
    pass