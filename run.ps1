# Start Python job in background, stream output
$job = Start-Job -ScriptBlock {
    .venv\Scripts\Activate.ps1
    $env:PYTHONIOENCODING = "utf-8"
    python .\main_process.py
} | Tee-Object -FilePath .\misc\out.log -Encoding utf8

# Monitor live output
Receive-Job $job -Keep
Get-Job $job | Wait-Job | Receive-Job
