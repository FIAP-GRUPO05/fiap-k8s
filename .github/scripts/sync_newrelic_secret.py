"""Copy repository credentials to the project's AWS secret without logging values."""
import json
import os
import subprocess
import tempfile

credentials = {
    "license_key": os.environ["NEW_RELIC_LICENSE_KEY"],
    "api_key": os.environ["NEW_RELIC_API_KEY"],
    "account_id": os.environ["NEW_RELIC_ACCOUNT_ID"],
}
if not credentials["license_key"] or not credentials["api_key"] or not credentials["account_id"].isdigit():
    raise ValueError("Configure the three NEW_RELIC repository secrets before deploying observability")
with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as secret_file:
    json.dump(credentials, secret_file)
    secret_file.flush()
    subprocess.run(["aws", "secretsmanager", "put-secret-value", "--secret-id", "fiap/shared/newrelic",
                    "--secret-string", f"file://{secret_file.name}"], capture_output=True, text=True, check=True)
print("New Relic credentials synchronized with AWS Secrets Manager")
