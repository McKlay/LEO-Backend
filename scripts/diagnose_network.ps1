# Phase 1.E Network Diagnostics Script
# Helps diagnose Supabase connectivity issues

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Phase 1.E: Network Connectivity Diagnostics" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Load Supabase URL from .env
$supabaseUrl = ""
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*SUPABASE_URL\s*=\s*"?([^"]+)"?\s*$') {
            $supabaseUrl = $matches[1]
        }
    }
}

if (-not $supabaseUrl) {
    Write-Host "❌ ERROR: Could not find SUPABASE_URL in .env file" -ForegroundColor Red
    exit 1
}

Write-Host "Supabase URL: $supabaseUrl" -ForegroundColor Green
Write-Host ""

# Extract hostname
$hostname = ([System.Uri]$supabaseUrl).Host
Write-Host "Hostname: $hostname" -ForegroundColor Green
Write-Host ""

# Test 1: DNS Resolution
Write-Host "Test 1: DNS Resolution" -ForegroundColor Yellow
Write-Host "Running: nslookup $hostname" -ForegroundColor Gray
try {
    $dnsResult = Resolve-DnsName -Name $hostname -ErrorAction Stop
    Write-Host "✅ DNS Resolution: SUCCESS" -ForegroundColor Green
    Write-Host "   IP Addresses:" -ForegroundColor Gray
    $dnsResult | Where-Object { $_.Type -eq 'A' } | ForEach-Object {
        Write-Host "   - $($_.IPAddress)" -ForegroundColor Gray
    }
} catch {
    Write-Host "❌ DNS Resolution: FAILED" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "DIAGNOSIS:" -ForegroundColor Yellow
    Write-Host "  - DNS server cannot resolve $hostname" -ForegroundColor White
    Write-Host "  - Check your DNS settings" -ForegroundColor White
    Write-Host "  - Try using Google DNS: 8.8.8.8, 8.8.4.4" -ForegroundColor White
    Write-Host "  - Check if VPN is required" -ForegroundColor White
}
Write-Host ""

# Test 2: Ping
Write-Host "Test 2: ICMP Ping" -ForegroundColor Yellow
Write-Host "Running: ping $hostname -n 2" -ForegroundColor Gray
try {
    $pingResult = Test-Connection -ComputerName $hostname -Count 2 -ErrorAction Stop
    Write-Host "✅ Ping: SUCCESS" -ForegroundColor Green
    Write-Host "   Average latency: $([math]::Round(($pingResult | Measure-Object -Property ResponseTime -Average).Average, 2))ms" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Ping: FAILED (may be blocked by firewall)" -ForegroundColor Yellow
    Write-Host "   Note: Ping failure doesn't always mean connection won't work" -ForegroundColor Gray
}
Write-Host ""

# Test 3: TCP Connection
Write-Host "Test 3: TCP Connection (Port 443)" -ForegroundColor Yellow
Write-Host "Testing HTTPS connectivity..." -ForegroundColor Gray
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect($hostname, 443)
    Write-Host "✅ TCP Connection: SUCCESS" -ForegroundColor Green
    $tcpClient.Close()
} catch {
    Write-Host "❌ TCP Connection: FAILED" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "DIAGNOSIS:" -ForegroundColor Yellow
    Write-Host "  - Port 443 (HTTPS) is blocked" -ForegroundColor White
    Write-Host "  - Check firewall rules" -ForegroundColor White
    Write-Host "  - Corporate proxy may be blocking connection" -ForegroundColor White
}
Write-Host ""

# Test 4: HTTP Request
Write-Host "Test 4: HTTP Request" -ForegroundColor Yellow
Write-Host "Running: curl $supabaseUrl" -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri $supabaseUrl -Method Get -UseBasicParsing -ErrorAction Stop
    Write-Host "✅ HTTP Request: SUCCESS" -ForegroundColor Green
    Write-Host "   Status Code: $($response.StatusCode)" -ForegroundColor Gray
    Write-Host "   Response Headers:" -ForegroundColor Gray
    $response.Headers.GetEnumerator() | Select-Object -First 5 | ForEach-Object {
        Write-Host "   - $($_.Key): $($_.Value)" -ForegroundColor Gray
    }
} catch {
    Write-Host "❌ HTTP Request: FAILED" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    if ($_.Exception.Message -like "*SSL*" -or $_.Exception.Message -like "*certificate*") {
        Write-Host "DIAGNOSIS:" -ForegroundColor Yellow
        Write-Host "  - SSL/TLS certificate issue" -ForegroundColor White
        Write-Host "  - Corporate proxy may be intercepting HTTPS" -ForegroundColor White
        Write-Host "  - Install corporate root certificate if needed" -ForegroundColor White
    }
}
Write-Host ""

# Test 5: Supabase API
Write-Host "Test 5: Supabase REST API" -ForegroundColor Yellow
$apiUrl = "$supabaseUrl/rest/v1/"
Write-Host "Running: curl $apiUrl" -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri $apiUrl -Method Get -UseBasicParsing -ErrorAction Stop
    Write-Host "✅ Supabase API: ACCESSIBLE" -ForegroundColor Green
    Write-Host "   Status Code: $($response.StatusCode)" -ForegroundColor Gray
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "✅ Supabase API: ACCESSIBLE (expected 404)" -ForegroundColor Green
        Write-Host "   Supabase is reachable and responding" -ForegroundColor Gray
    } else {
        Write-Host "❌ Supabase API: FAILED" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host ""

# Test 6: Python connectivity
Write-Host "Test 6: Python HTTP Request" -ForegroundColor Yellow
Write-Host "Testing with Python httpx library..." -ForegroundColor Gray
$pythonCode = @"
import httpx
import sys

url = '$supabaseUrl'
try:
    response = httpx.get(url, timeout=10.0)
    print(f'✅ Python httpx: SUCCESS (Status: {response.status_code})')
    sys.exit(0)
except httpx.ConnectError as e:
    print(f'❌ Python httpx: CONNECT ERROR - {str(e)}')
    sys.exit(1)
except Exception as e:
    print(f'⚠️  Python httpx: ERROR - {str(e)}')
    sys.exit(1)
"@

try {
    $result = .venv\Scripts\python.exe -c $pythonCode
    Write-Host $result
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "DIAGNOSIS:" -ForegroundColor Yellow
        Write-Host "  - Python httpx library cannot connect" -ForegroundColor White
        Write-Host "  - This is the same error blocking integration tests" -ForegroundColor White
        Write-Host "  - Fix network connectivity to resolve" -ForegroundColor White
    }
} catch {
    Write-Host "❌ Python test failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Summary
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "SUMMARY & RECOMMENDATIONS" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Review test results above" -ForegroundColor White
Write-Host "2. If DNS failed: Fix DNS configuration or use different network" -ForegroundColor White
Write-Host "3. If TCP failed: Check firewall rules and proxy settings" -ForegroundColor White
Write-Host "4. If HTTP failed: Check SSL certificates and corporate proxy" -ForegroundColor White
Write-Host "5. If Python failed: This is your blocker - fix issues above first" -ForegroundColor White
Write-Host ""

Write-Host "Common Solutions:" -ForegroundColor Yellow
Write-Host "• Connect to different network (mobile hotspot, home WiFi)" -ForegroundColor White
Write-Host "• Configure corporate VPN if required" -ForegroundColor White
Write-Host "• Add firewall exception for *.supabase.co" -ForegroundColor White
Write-Host "• Update DNS to use 8.8.8.8 (Google DNS)" -ForegroundColor White
Write-Host "• Contact IT support for network access" -ForegroundColor White
Write-Host ""

Write-Host "=================================================" -ForegroundColor Cyan
