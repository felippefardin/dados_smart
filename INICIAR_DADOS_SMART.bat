@echo off
title Dados Smart - Servidor
cd /d C:\xampp\htdocs\dados_smart
echo Iniciando o servidor Dados Smart...
echo Mantenha esta janela aberta enquanto estiver usando o sistema.
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8001
echo.
echo O servidor foi encerrado ou ocorreu um erro.
pause
