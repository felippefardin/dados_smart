$ErrorActionPreference = "SilentlyContinue"
$projeto = "C:\xampp\htdocs\dados_smart"
$urlSaude = "http://127.0.0.1:8001/health"
$urlSistema = "http://localhost/dados_smart/login.html"

$servidorAtivo = $false
try {
    $resposta = Invoke-RestMethod -Uri $urlSaude -TimeoutSec 2
    $servidorAtivo = ($resposta.status -eq "ok" -and $resposta.banco -eq "mysql")
} catch {
    $servidorAtivo = $false
}

if (-not $servidorAtivo) {
    Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001" `
        -WorkingDirectory $projeto `
        -WindowStyle Hidden

    for ($tentativa = 0; $tentativa -lt 15; $tentativa++) {
        Start-Sleep -Milliseconds 500
        try {
            $resposta = Invoke-RestMethod -Uri $urlSaude -TimeoutSec 2
            if ($resposta.status -eq "ok") {
                $servidorAtivo = $true
                break
            }
        } catch {}
    }
}

if ($servidorAtivo) {
    Start-Process $urlSistema
} else {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Não foi possível iniciar o servidor Dados Smart. Confirme se o Apache e o MySQL estão ativos no XAMPP.",
        "Dados Smart",
        "OK",
        "Error"
    ) | Out-Null
}
