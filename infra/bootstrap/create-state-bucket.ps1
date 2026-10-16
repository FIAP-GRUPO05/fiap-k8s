param(
    [string]$Profile = 'fiap-team'
)

$ErrorActionPreference = 'Stop'
$accountId = '456687462806'
$region = 'sa-east-1'
$bucket = "fiap-tfstate-$accountId"
$encryptionFile = (Join-Path $PSScriptRoot 'bucket-encryption.json').Replace('\', '/')
$encryptionInput = "file://$encryptionFile"

$actualAccount = aws sts get-caller-identity --profile $Profile --query Account --output text
if ($LASTEXITCODE -ne 0 -or $actualAccount.Trim() -ne $accountId) {
    throw "O perfil $Profile nao esta autenticado na conta $accountId."
}

$actualArn = aws sts get-caller-identity --profile $Profile --query Arn --output text
if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel verificar a identidade do perfil $Profile."
}
if ($actualArn.Trim().EndsWith(':root')) {
    throw 'Nao execute o bootstrap com a identidade root. Configure MFA e uma identidade administrativa do time.'
}

$existing = aws s3api list-buckets --profile $Profile --query "Buckets[?Name=='$bucket'].Name" --output text
if ($LASTEXITCODE -ne 0) {
    throw 'Nao foi possivel listar os buckets da conta.'
}

if ([string]::IsNullOrWhiteSpace($existing)) {
    aws s3api create-bucket --profile $Profile --region $region --bucket $bucket --create-bucket-configuration "LocationConstraint=$region" --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o bucket $bucket." }
}

aws s3api put-public-access-block --profile $Profile --bucket $bucket --expected-bucket-owner $accountId --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true' --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'Falha ao bloquear o acesso publico ao bucket.' }

aws s3api put-bucket-encryption --profile $Profile --bucket $bucket --expected-bucket-owner $accountId --server-side-encryption-configuration $encryptionInput --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'Falha ao configurar a criptografia do bucket.' }

aws s3api put-bucket-versioning --profile $Profile --bucket $bucket --expected-bucket-owner $accountId --versioning-configuration 'Status=Enabled' --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'Falha ao habilitar versionamento do bucket.' }

Write-Output "Bucket de estado pronto: $bucket ($region)."

