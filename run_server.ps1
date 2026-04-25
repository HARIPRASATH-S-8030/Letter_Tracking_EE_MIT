# Set your ESP32 device IP and optional token then run the Flask app
# Usage:
#   .\run_server.ps1                      # uses embedded default if present
#   .\run_server.ps1 192.168.43.8         # override ESP32 host for this run
#   $env:ESP32_HOST = '...' ; .\run_server.ps1  # also supported

# Prefer explicit args, then environment, then fallback defaults
# Usage: .\run_server.ps1 [INBOX_HOST] [STAFF_HOST]
if ($args.Count -ge 2) {
	$env:ESP32_INBOX_HOST = $args[0]
	$env:ESP32_STAFF_HOST = $args[1]
} elseif ($args.Count -eq 1 -and $args[0]) {
	# single arg: use for both
	$env:ESP32_INBOX_HOST = $args[0]
	$env:ESP32_STAFF_HOST = $args[0]
} else {
	if (-not $env:ESP32_INBOX_HOST) { $env:ESP32_INBOX_HOST = $env:ESP32_HOST }
	if (-not $env:ESP32_STAFF_HOST) { $env:ESP32_STAFF_HOST = $env:ESP32_HOST }
	if (-not $env:ESP32_INBOX_HOST) { $env:ESP32_INBOX_HOST = '192.168.43.8' }
	if (-not $env:ESP32_STAFF_HOST) { $env:ESP32_STAFF_HOST = '192.168.43.9' }
}

Write-Host "Starting server with ESP32_INBOX_HOST=$($env:ESP32_INBOX_HOST) ESP32_STAFF_HOST=$($env:ESP32_STAFF_HOST)"

# Optional: set a token to require ESP devices to include it
# $env:ESP_TOKEN = 'your-secret-token'

# Run Flask (unbuffered output)
python -u app.py
