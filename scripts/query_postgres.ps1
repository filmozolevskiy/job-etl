# PowerShell script to connect to PostgreSQL database
# Usage: .\scripts\query_postgres.ps1 [query]
# Example: .\scripts\query_postgres.ps1 "SELECT COUNT(*) FROM raw.job_postings_raw;"

param(
    [string]$Query = ""
)

$containerName = "job-etl-postgres"
$dbUser = "job_etl_user"
$dbName = "job_etl"

# Read password from secrets file
$passwordFile = "./secrets/database/postgres_password.txt"
if (Test-Path $passwordFile) {
    $password = Get-Content $passwordFile -Raw | ForEach-Object { $_.Trim() }
} else {
    Write-Host "Error: Password file not found at $passwordFile" -ForegroundColor Red
    exit 1
}

# Set PGPASSWORD environment variable for psql
$env:PGPASSWORD = $password

if ($Query -eq "") {
    # Interactive mode
    Write-Host "Connecting to PostgreSQL..." -ForegroundColor Green
    Write-Host "Database: $dbName | User: $dbUser" -ForegroundColor Cyan
    Write-Host "Type \q to exit" -ForegroundColor Yellow
    Write-Host ""
    docker exec -it $containerName psql -U $dbUser -d $dbName
} else {
    # Execute query
    Write-Host "Executing query..." -ForegroundColor Green
    docker exec $containerName psql -U $dbUser -d $dbName -c $Query
}

