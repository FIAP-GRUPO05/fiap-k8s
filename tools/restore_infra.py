"""Administrative reconstruction after destroy; no provisioning without --execute.

Uses the four sibling repositories, saved Terraform plans and retained IAM imports.
Keeps CI in maintenance until explicitly activated after real validation.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ACCOUNT = "456687462806"
REGION = "sa-east-1"
BUCKET = "fiap-tfstate-" + ACCOUNT
PROJECT = "fiap-tech-challenge-fase-3"
REPOS = ("fiap-k8s", "fiap-database", "fiap-lambda", "fiap-application")
ENVS = ("develop", "homol", "prod")


class Restore:
    def __init__(self, workspace, profile, sender=None, recipient=None, execute=False, trivy="trivy"):
        self.workspace, self.execute = Path(workspace).resolve(), execute
        self.sender, self.recipient = sender, recipient
        self.newrelic_imports = {}
        self.trivy = trivy
        self.env = dict(os.environ, AWS_PROFILE=profile, AWS_DEFAULT_REGION=REGION, AWS_REGION=REGION,
                        AWS_PAGER="", TF_IN_AUTOMATION="1", TF_INPUT="false")
        if sender:
            self.env["TF_VAR_notification_sender"] = sender

    def run(self, args, cwd=None, input=None, mutation=False, missing=False):
        if mutation and not self.execute:
            raise PermissionError("Use --execute for an administrative mutation")
        result = subprocess.run(args, cwd=cwd, env=self.env, input=input, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            if missing and any(code in result.stderr for code in
                ("NoSuchEntity", "NoSuchBucket", "ResourceNotFoundException", "NotFoundException", "ImageNotFoundException")):
                return None
            # Do not print stdout from commands which can return secret values.
            raise RuntimeError(f"{args[0]} {args[1]} failed: {result.stderr[:700]}")
        return result.stdout

    def aws(self, service, operation, *args, mutation=False, missing=False):
        body = self.run(["aws", service, operation, *args, "--region", REGION, "--output", "json"],
                        mutation=mutation, missing=missing)
        return json.loads(body) if body and body.strip() else None

    def identity(self):
        account = self.aws("sts", "get-caller-identity")
        if account["Account"] != ACCOUNT:
            raise PermissionError("Wrong AWS account; reconstruction refused")
        return account

    def variables(self, state):
        for repo in REPOS:
            self.run(["gh", "variable", "set", "FIAP_INFRA_STATE", "--repo", "FIAP-GRUPO05/" + repo,
                      "--body", state], mutation=True)

    def control(self, state):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.json"
            path.write_text(json.dumps({"state": state, "operation": "administrative-reconstruction"}), encoding="utf-8")
            self.aws("s3api", "put-object", "--bucket", BUCKET, "--key", "fiap/operations/state.json",
                     "--body", str(path), mutation=True)

    def prepare(self):
        self.identity()
        if not self.sender or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.sender):
            raise ValueError("Provide --sender with the authorized SES email address")
        identity = self.aws("sesv2", "get-email-identity", "--email-identity", self.sender, missing=True)
        if identity is None:
            self.aws("sesv2", "create-email-identity", "--email-identity", self.sender,
                     "--tags", "Key=Project,Value=" + PROJECT, mutation=True)
            raise RuntimeError("SES verification requested. Confirm the email, then resume before creating EKS/RDS")
        if not identity.get("VerifiedForSendingStatus"):
            raise RuntimeError("Confirm the SES sender verification before creating EKS/RDS")
        buckets = self.aws("s3api", "list-buckets")["Buckets"]
        if not any(item["Name"] == BUCKET for item in buckets):
            self.aws("s3api", "create-bucket", "--bucket", BUCKET,
                     "--create-bucket-configuration", "LocationConstraint=" + REGION, mutation=True)
        self.aws("s3api", "put-public-access-block", "--bucket", BUCKET, "--public-access-block-configuration",
                 "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true", mutation=True)
        self.aws("s3api", "put-bucket-versioning", "--bucket", BUCKET,
                 "--versioning-configuration", "Status=Enabled", mutation=True)
        self.aws("s3api", "put-bucket-encryption", "--bucket", BUCKET, "--server-side-encryption-configuration",
                 json.dumps({"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}), mutation=True)
        self.control("maintenance")
        self.variables("maintenance")
        secrets = self.aws("secretsmanager", "list-secrets", "--include-planned-deletion")["SecretList"]
        for item in secrets:
            if item["Name"].startswith("fiap/") and item.get("DeletedDate"):
                self.aws("secretsmanager", "restore-secret", "--secret-id", item["ARN"], mutation=True)
        print("State backend secured; retained secrets restored; CI remains in maintenance")

    @staticmethod
    def no_deletions(plan):
        for item in plan.get("resource_changes", []):
            if "delete" in item["change"]["actions"]:
                raise PermissionError("Reconstruction refuses deletion/replacement: " + item["address"])

    def import_id(self, item):
        if item["type"].startswith("newrelic_"):
            return self.newrelic_imports.get(item["address"])
        kind, after = item["type"], item["change"].get("after") or {}
        name = after.get("name", "")
        if kind == "aws_iam_openid_connect_provider" and after.get("url") == "https://token.actions.githubusercontent.com":
            arn = f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"
            return arn if self.aws("iam", "get-open-id-connect-provider", "--open-id-connect-provider-arn", arn, missing=True) else None
        if kind == "aws_iam_role" and name.startswith("fiap-"):
            return name if self.aws("iam", "get-role", "--role-name", name, missing=True) else None
        if kind == "aws_iam_role_policy" and name.startswith("fiap-") and (after.get("role") or "").startswith("fiap-"):
            role = after["role"]
            return role + ":" + name if self.aws("iam", "get-role-policy", "--role-name", role,
                                                "--policy-name", name, missing=True) else None
        if kind == "aws_iam_policy" and name.startswith("fiap-"):
            arn = f"arn:aws:iam::{ACCOUNT}:policy/{name}"
            return arn if self.aws("iam", "get-policy", "--policy-arn", arn, missing=True) else None
        if kind == "aws_iam_role_policy_attachment" and (after.get("role") or "").startswith("fiap-") and after.get("policy_arn"):
            attached = self.aws("iam", "list-attached-role-policies", "--role-name", after["role"], missing=True) or {}
            if any(p["PolicyArn"] == after["policy_arn"] for p in attached.get("AttachedPolicies", [])):
                return after["role"] + "/" + after["policy_arn"]
        if kind == "aws_secretsmanager_secret" and name.startswith("fiap/"):
            secret = self.aws("secretsmanager", "describe-secret", "--secret-id", name, missing=True)
            return secret["ARN"] if secret else None
        if kind == "aws_kms_alias" and name.startswith("alias/fiap-"):
            aliases = self.aws("kms", "list-aliases")["Aliases"]
            return name if any(a["AliasName"] == name for a in aliases) else None
        return None

    def terraform(self, repo, relative, *variables):
        path = self.workspace / repo / relative
        self.run(["terraform", "init", "-reconfigure", "-backend-config=backend.hcl", "-input=false"], path)
        for attempt in range(4):
            lock = [] if self.execute else ["-lock=false"]
            self.run(["terraform", "plan", "-input=false", "-out=restore.tfplan", *lock, *variables], path)
            plan = json.loads(self.run(["terraform", "show", "-json", "restore.tfplan"], path))
            self.no_deletions(plan)
            if not self.execute:
                print(f"Reviewed plan generated for {repo}/{relative}; no apply performed")
                return
            imports = 0
            for item in plan.get("resource_changes", []):
                if item["change"]["actions"] == ["create"] and (identifier := self.import_id(item)):
                    self.run(["terraform", "import", "-input=false", *variables, item["address"], identifier], path, mutation=True)
                    imports += 1
            if not imports:
                self.run(["terraform", "apply", "-input=false", "-auto-approve", "restore.tfplan"], path, mutation=True)
                print(f"Applied {repo}/{relative}; retained resources reconciled")
                return
        raise RuntimeError("Import reconciliation did not converge; no plan applied")

    def observability(self):
        import newrelic_reconcile
        credentials = json.loads(self.aws("secretsmanager", "get-secret-value", "--secret-id", "fiap/shared/newrelic")["SecretString"])
        account = int(credentials["account_id"])
        self.newrelic_imports = newrelic_reconcile.imports(account, newrelic_reconcile.client(credentials))
        values = {"TF_VAR_api_key": credentials["api_key"], "TF_VAR_account_id": str(account), "TF_VAR_region": credentials.get("region", "US")}
        previous = {key: self.env.get(key) for key in values}
        try:
            self.env.update(values)
            self.terraform("fiap-k8s", "infra/observability")
        finally:
            for key, value in previous.items():
                if value is None: self.env.pop(key, None)
                else: self.env[key] = value

    def codebuild(self, project, **overrides):
        args = ["--project-name", project]
        if overrides:
            args += ["--environment-variables-override", json.dumps([
                {"name": key, "value": value, "type": "PLAINTEXT"} for key, value in overrides.items()])]
        build = self.aws("codebuild", "start-build", *args, mutation=True)["build"]["id"]
        self.run([sys.executable, str(self.workspace / "fiap-k8s/.github/scripts/wait_codebuild.py"), build])

    def output(self, repo, relative, name):
        return json.loads(self.run(["terraform", "output", "-json", name], self.workspace / repo / relative))

    def runtime(self):
        config = self.output("fiap-lambda", "infra/managed", "runtime_config")
        if set(config) != set(ENVS):
            raise ValueError("Expected exactly develop, homol and prod")
        for environment, settings in config.items():
            if not re.fullmatch(r"https://[a-z0-9]+\.execute-api\.sa-east-1\.amazonaws\.com", settings["api_url"]):
                raise ValueError("Unexpected API Gateway endpoint")
            if settings["issuer"] != settings["api_url"]:
                raise ValueError("Unexpected issuer")
            settings["notification_test_email"] = self.recipient or ""
        return config

    def sync(self):
        config = self.runtime()
        for repo in REPOS:
            self.run(["gh", "variable", "set", "FIAP_RUNTIME_CONFIG", "--repo", "FIAP-GRUPO05/" + repo,
                      "--body", json.dumps(config)], mutation=True)
        if self.sender:
            self.run(["gh", "variable", "set", "FIAP_NOTIFICATION_SENDER", "--repo", "FIAP-GRUPO05/fiap-lambda",
                      "--body", self.sender], mutation=True)
        endpoints = {env: settings["api_url"] for env, settings in config.items()}
        self.terraform("fiap-k8s", "infra/platform", "-var=api_endpoints=" + json.dumps(endpoints))
        print("Runtime variables and uptime endpoints synchronized; CI still in maintenance")

    def packages(self):
        path = self.workspace / "fiap-lambda"
        build = path / "build"
        build.mkdir(exist_ok=True)
        self.run(["docker", "run", "--rm", "--entrypoint", "python", "-v", f"{path}:/src:ro", "-v", f"{build}:/build",
                  "public.ecr.aws/lambda/python:3.12", "-m", "pip", "install", "--no-compile", "-r", "/src/requirements.txt",
                  "--target", "/build/token-package"])
        shutil.copyfile(path / "codetoken/main.py", build / "token-package/main.py")
        shutil.make_archive(str(build / "token"), "zip", build / "token-package")
        with zipfile.ZipFile(build / "email.zip", "w", zipfile.ZIP_DEFLATED) as package:
            package.write(path / "codeemail/main.py", "main.py")

    def keys(self):
        python = self.workspace / "fiap-lambda/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        for environment in ENVS:
            name = f"fiap/{environment}/jwt-signing"
            meta = self.aws("secretsmanager", "describe-secret", "--secret-id", name)
            if any("AWSCURRENT" in stages for stages in meta.get("VersionIdsToStages", {}).values()):
                continue
            with tempfile.TemporaryDirectory() as directory:
                key = Path(directory) / "key.pem"
                code = ("from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; "
                        "from pathlib import Path; import sys; k=rsa.generate_private_key(public_exponent=65537,key_size=2048); "
                        "Path(sys.argv[1]).write_bytes(k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))")
                self.run([str(python), "-c", code, str(key)])
                self.aws("secretsmanager", "put-secret-value", "--secret-id", name,
                         "--secret-string", "file://" + str(key), mutation=True)
                if environment == "prod":
                    self.run(["gh", "secret", "set", "JWT_PRIVATE_KEY", "--repo", "FIAP-GRUPO05/fiap-lambda"],
                             input=key.read_text(), mutation=True)

    def application(self):
        self.run([self.trivy, "--version"])
        path = self.workspace / "fiap-application"
        if self.run(["git", "status", "--porcelain"], path).strip():
            raise RuntimeError("Commit the reviewed application before publishing an immutable image")
        sha = self.run(["git", "rev-parse", "HEAD"], path).strip()
        image = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/fiap-application:restore-{sha}"
        self.terraform("fiap-application", "infra/registry")
        password = self.run(["aws", "ecr", "get-login-password", "--region", REGION])
        self.run(["docker", "login", "--username", "AWS", "--password-stdin", image.split("/")[0]], input=password, mutation=True)
        self.run(["docker", "build", "--pull", "--tag", image, "."], path)
        self.run([self.trivy, "image", "--severity", "HIGH,CRITICAL", "--exit-code", "1",
                  "--ignorefile", str(path / ".trivyignore"), image], path)
        self.run(["docker", "push", image], mutation=True)
        config = self.runtime()
        for environment in ENVS:
            self.codebuild("fiap-eks-deploy", IMAGE_URI=image, DEPLOY_NAMESPACE=environment, JWT_ISSUER=config[environment]["issuer"])
        self.codebuild("fiap-database-bootstrap")

    def validate(self):
        if not self.recipient:
            raise ValueError("--test-recipient is required for authorized notification regression")
        config = self.runtime()
        self.env["FIAP_RUNTIME_CONFIG"] = json.dumps(config)
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "uptime.json"
            self.aws("lambda", "invoke", "--function-name", "fiap-uptime-probe", str(result), mutation=True)
            if not json.loads(result.read_text()).get("healthy", False):
                # The live regression below checks the authoritative New Relic ingestion status.
                print("Uptime probe invoked; checking telemetry during the live regressions")
        for environment in ENVS:
            self.run([sys.executable, ".github/scripts/live_regression.py", environment], self.workspace / "fiap-application", mutation=True)
        print("All live regressions passed; activation remains an explicit final operation")

    def stage(self, stage):
        self.identity()
        if stage == "status":
            print(json.dumps({"account": ACCOUNT, "region": REGION, "session": "authenticated"}))
        elif stage == "prepare": self.prepare()
        elif stage == "bootstrap": self.terraform("fiap-k8s", "infra/bootstrap")
        elif stage == "platform":
            self.terraform("fiap-k8s", "infra/platform", "-var=api_endpoints={}")
            if self.execute: self.codebuild("fiap-platform-bootstrap")
        elif stage == "observability": self.observability()
        elif stage == "database":
            self.terraform("fiap-database", "infra/managed")
            if self.execute: self.codebuild("fiap-database-bootstrap")
        elif stage == "lambda":
            self.packages()
            self.terraform("fiap-lambda", "infra/managed", "-var=enable_backend_proxy=false")
            if self.execute: self.keys()
        elif stage == "application": self.application()
        elif stage == "gateway":
            self.terraform("fiap-lambda", "infra/managed")
            if self.execute:
                for environment in ENVS:
                    for script, package in (("deploy_lambda.py", "token.zip"), ("deploy_notifications.py", "email.zip")):
                        self.run([sys.executable, ".github/scripts/" + script, environment, "build/" + package], self.workspace / "fiap-lambda", mutation=True)
        elif stage == "sync": self.sync()
        elif stage == "validate": self.validate()
        elif stage == "activate":
            self.validate()
            self.variables("active")
            self.control("active")
        elif stage == "all":
            if not self.execute or not self.recipient:
                raise ValueError("Full reconstruction requires --execute and --test-recipient")
            for name in ("prepare", "bootstrap", "platform", "observability", "database", "lambda", "application", "gateway", "sync", "validate"):
                print("Reconstruction stage:", name, flush=True)
                self.stage(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--profile", default="twm-admin-terraform")
    parser.add_argument("--sender")
    parser.add_argument("--test-recipient")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--trivy", default="trivy", help="Trivy executable used before publishing the rebuilt image")
    parser.add_argument("--stage", default="status", choices=["status", "prepare", "bootstrap", "platform", "observability", "database", "lambda", "application", "gateway", "sync", "validate", "activate", "all"])
    args = parser.parse_args()
    try:
        Restore(args.workspace, args.profile, args.sender, args.test_recipient, args.execute, args.trivy).stage(args.stage)
    except (RuntimeError, PermissionError, ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
