"""Scoped AWS CLI teardown engine. No mutation is available in its default mode."""
import datetime as dt
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ACCOUNT = "456687462806"
REGION = "sa-east-1"
PROJECT = "fiap-tech-challenge-fase-3"
BUCKET = "fiap-tfstate-" + ACCOUNT
CONTROL = "fiap/operations/state.json"
CLUSTER = "fiap-shared"
FUNCTIONS = {"fiap-auth-develop", "fiap-auth-homol", "fiap-auth-prod", "fiap-email-develop", "fiap-email-homol", "fiap-email-prod", "fiap-uptime-probe", "fiap-observability-probe"}
APIS = {"fiap-develop", "fiap-homol", "fiap-prod"}
BUILDS = {"fiap-platform-bootstrap", "fiap-database-bootstrap", "fiap-eks-deploy"}
LOG_GROUPS = ({"/aws/lambda/" + name for name in FUNCTIONS}
              | {"/aws/apigateway/" + name for name in APIS}
              | {"/aws/codebuild/" + name for name in BUILDS}
              | {"/aws/eks/fiap-shared/cluster", "/aws/rds/instance/fiap-shared-postgres/postgresql", "/aws/rds/instance/fiap-shared-postgres/upgrade"})


class Aws:
    def __init__(self, *, destructive=False):
        self.destructive = destructive

    def run(self, service, operation, *arguments, query=None, mutation=False, missing=False, region=REGION):
        if mutation and (not self.destructive or os.environ.get("GITHUB_REF_NAME") != "ALL"
                         or os.environ.get("GITHUB_EVENT_NAME") != "push"
                         or not os.environ.get("FIAP_APPROVED_DESTROY_REQUEST")):
            raise PermissionError("AWS mutation requires the reviewed ALL execution")
        if mutation and region != REGION:
            raise PermissionError("Mutation outside the project region is forbidden")
        command = ["aws", service, operation, *arguments, "--region", region, "--output", "json", "--no-cli-pager"]
        if query:
            command += ["--query", query]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180,
                                env=dict(os.environ, AWS_PAGER="", AWS_RETRY_MODE="adaptive", AWS_MAX_ATTEMPTS="5"))
        if result.returncode:
            error = result.stderr.strip()
            if missing and any(code in error for code in ("ResourceNotFound", "DBInstanceNotFound", "DBSnapshotNotFound", "LoadBalancerNotFound", "NoSuchBucket", "NoSuchKey", "RepositoryNotFound", "NotFoundException", "InvalidGroup.NotFound", "InvalidSecurityGroupRuleId.NotFound", "InvalidVpcID.NotFound", "InvalidVpcEndpointId.NotFound")):
                return None
            raise RuntimeError(f"{service}/{operation}: {error[:1800]}")
        return json.loads(result.stdout) if result.stdout.strip() else None

    def identity(self):
        identity = self.run("sts", "get-caller-identity")
        if identity["Account"] != ACCOUNT:
            raise PermissionError("Unexpected AWS account")
        return identity

    def change(self, service, operation, *arguments, **kwargs):
        return self.run(service, operation, *arguments, mutation=True, **kwargs)

    def control_state(self, state):
        # If the state bucket was already removed, GitHub variables remain frozen.
        names = self.run("s3api", "list-buckets", query="Buckets[].Name") or []
        if BUCKET not in names:
            return
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"state": state, "run": os.environ.get("GITHUB_RUN_ID")}), encoding="utf-8")
            self.change("s3api", "put-object", "--bucket", BUCKET, "--key", CONTROL, "--body", str(path))

    def stop_builds(self):
        projects = self.run("codebuild", "list-projects", query="projects") or []
        for project in sorted(set(projects) & BUILDS):
            ids = self.run("codebuild", "list-builds-for-project", "--project-name", project, query="ids") or []
            for offset in range(0, len(ids), 100):
                for build in self.run("codebuild", "batch-get-builds", "--ids", *ids[offset:offset + 100],
                                      query="builds[].{Id:id,Complete:buildComplete}") or []:
                    if not build["Complete"]:
                        self.change("codebuild", "stop-build", "--id", build["Id"])
                        for _ in range(90):
                            complete = self.run("codebuild", "batch-get-builds", "--ids", build["Id"], query="builds[0].buildComplete")
                            if complete:
                                break
                            time.sleep(2)
                        else:
                            raise RuntimeError("CodeBuild did not stop")


def tags(values):
    return {item.get("Key", item.get("key")): item.get("Value", item.get("value")) for item in values or []}


def owned(values):
    mapping = tags(values)
    return mapping.get("Project") == PROJECT or mapping.get("elbv2.k8s.aws/cluster") == CLUSTER or mapping.get("aws:eks:cluster-name") == CLUSTER or mapping.get("eks:cluster-name") == CLUSTER or mapping.get("kubernetes.io/cluster/" + CLUSTER) in {"owned", "shared"}


def resource_keys(result):
    keys = {(item["kind"], item["id"]) for item in result.get("resources", [])}
    for item in result.get("resources", []):
        keys.update(("vpc-child", identifier) for identifier in item.get("children", []))
    return keys


def covered_identifier(service, candidates, report):
    kinds = {"ec2": {"ec2", "volume", "ebs-snapshot", "nat", "eip", "endpoint", "vpc"},
             "eks": {"eks"}, "rds": {"rds", "rds-snapshot", "rds-backup", "rds-subnet-group"},
             "lambda": {"lambda"}, "apigateway": {"api", "vpc-link"}, "kms": {"kms", "aws-managed-kms"},
             "ecr": {"ecr"}, "s3": {"bucket"}, "logs": {"logs"}, "codebuild": {"codebuild"},
             "events": {"rule"}, "autoscaling": {"asg"}, "secretsmanager": {"secret"}, "ses": {"ses-identity"}}
    accepted = set()
    for item in report["resources"] + report["free_resources"]:
        if item["kind"] in kinds.get(service, set()):
            accepted.add(item["id"])
            if service == "ec2":
                accepted.update(item.get("children", []))
    return bool(candidates & accepted)


def inventory(client=None):
    aws = client or Aws()
    aws.identity()
    report = {"captured_at": dt.datetime.now(dt.timezone.utc).isoformat(), "account": ACCOUNT,
              "region": REGION, "resources": [], "errors": [], "free_resources": []}

    def read(service, operation, *arguments, **kwargs):
        try:
            return aws.run(service, operation, *arguments, **kwargs)
        except Exception as error:
            report["errors"].append(str(error))
            return None

    def add(kind, identifier, **attributes):
        report["resources"].append({"kind": kind, "id": identifier, **attributes})

    vpcs = read("ec2", "describe-vpcs", "--filters", "Name=tag:Project,Values=" + PROJECT, query="Vpcs") or []
    vpcs = [vpc for vpc in vpcs if not vpc["IsDefault"] and tags(vpc.get("Tags")).get("Name") == "fiap-shared"]
    vpc_ids = {vpc["VpcId"] for vpc in vpcs}
    for vpc in vpcs:
        children = []
        for operation, field, identifier in (("describe-subnets", "Subnets", "SubnetId"),
                                            ("describe-security-groups", "SecurityGroups", "GroupId"),
                                            ("describe-network-interfaces", "NetworkInterfaces", "NetworkInterfaceId"),
                                            ("describe-route-tables", "RouteTables", "RouteTableId")):
            entries = read("ec2", operation, "--filters", "Name=vpc-id,Values=" + vpc["VpcId"], query=field) or []
            children += [entry[identifier] for entry in entries]
            if operation == "describe-security-groups":
                for entry in entries:
                    if entry["GroupName"] != "default" and not owned(entry.get("Tags")):
                        report["errors"].append("Security group ownership is uncertain: " + entry["GroupId"])
        group_ids = [identifier for identifier in children if identifier.startswith("sg-")]
        if group_ids:
            children += [entry["SecurityGroupRuleId"] for entry in read("ec2", "describe-security-group-rules", "--filters", "Name=group-id,Values=" + ",".join(group_ids), query="SecurityGroupRules") or []]
        children += [entry["InternetGatewayId"] for entry in read("ec2", "describe-internet-gateways", "--filters", "Name=attachment.vpc-id,Values=" + vpc["VpcId"], query="InternetGateways") or []]
        add("vpc", vpc["VpcId"], children=children)
    clusters = read("eks", "list-clusters", query="clusters") or []
    if CLUSTER in clusters:
        info = read("eks", "describe-cluster", "--name", CLUSTER, query="cluster")
        if info and info["resourcesVpcConfig"]["vpcId"] in vpc_ids:
            add("eks", CLUSTER, deletion_protection=info.get("deletionProtection", False))
            if read("eks", "list-fargate-profiles", "--cluster-name", CLUSTER, query="fargateProfileNames"):
                report["errors"].append("Unexpected Fargate profiles require an expanded reviewed plan")
        else:
            report["errors"].append("Cluster ownership/VPC mismatch")
    databases = read("rds", "describe-db-instances", query="DBInstances") or []
    for database in databases:
        if database["DBInstanceIdentifier"] == "fiap-shared-postgres" and owned(database.get("TagList")):
            add("rds", database["DBInstanceIdentifier"], protection=database["DeletionProtection"], status=database["DBInstanceStatus"])
        elif database["DBInstanceIdentifier"] == "fiap-shared-postgres":
            report["errors"].append("RDS ownership tags are missing or unexpected")
    for snapshot in read("rds", "describe-db-snapshots", query="DBSnapshots") or []:
        if snapshot["DBInstanceIdentifier"] == "fiap-shared-postgres" and snapshot["SnapshotType"] == "manual":
            add("rds-snapshot", snapshot["DBSnapshotIdentifier"])
    for backup in read("rds", "describe-db-instance-automated-backups", query="DBInstanceAutomatedBackups") or []:
        if backup["DBInstanceIdentifier"] == "fiap-shared-postgres" and backup["Status"] == "retained":
            add("rds-backup", backup["DbiResourceId"])
    for group in read("rds", "describe-db-subnet-groups", query="DBSubnetGroups") or []:
        if group["DBSubnetGroupName"] == "fiap-shared-postgres" and group["VpcId"] in vpc_ids:
            add("rds-subnet-group", group["DBSubnetGroupName"])
    for group in read("autoscaling", "describe-auto-scaling-groups", query="AutoScalingGroups") or []:
        if owned(group.get("Tags")) and group["AutoScalingGroupName"].startswith("eks-fiap-shared-"):
            add("asg", group["AutoScalingGroupName"])
    for reservation in read("ec2", "describe-instances", query="Reservations") or []:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] != "terminated" and owned(instance.get("Tags")) and instance.get("VpcId") in vpc_ids:
                add("ec2", instance["InstanceId"])
    for volume in read("ec2", "describe-volumes", query="Volumes") or []:
        if owned(volume.get("Tags")):
            add("volume", volume["VolumeId"])
    for snapshot in read("ec2", "describe-snapshots", "--owner-ids", ACCOUNT, query="Snapshots") or []:
        if owned(snapshot.get("Tags")):
            add("ebs-snapshot", snapshot["SnapshotId"])
    for nat in read("ec2", "describe-nat-gateways", query="NatGateways") or []:
        if nat["VpcId"] in vpc_ids and nat["State"] != "deleted":
            add("nat", nat["NatGatewayId"], addresses=nat.get("NatGatewayAddresses", []))
    for address in read("ec2", "describe-addresses", query="Addresses") or []:
        if owned(address.get("Tags")):
            add("eip", address["AllocationId"])
    for endpoint in read("ec2", "describe-vpc-endpoints", query="VpcEndpoints") or []:
        if endpoint["VpcId"] in vpc_ids and endpoint["State"] != "deleted":
            add("endpoint", endpoint["VpcEndpointId"], endpoint_type=endpoint["VpcEndpointType"])
    for lb in read("elbv2", "describe-load-balancers", query="LoadBalancers") or []:
        if lb["VpcId"] in vpc_ids and lb["LoadBalancerName"] == "fiap-shared-api":
            add("alb", lb["LoadBalancerArn"])
    for group in read("elbv2", "describe-target-groups", query="TargetGroups") or []:
        if group.get("VpcId") in vpc_ids:
            metadata = read("elbv2", "describe-tags", "--resource-arns", group["TargetGroupArn"], query="TagDescriptions[0].Tags")
            if metadata is not None and owned(metadata):
                add("target-group", group["TargetGroupArn"])
    for function in read("lambda", "list-functions", query="Functions[].{Name:FunctionName,Vpc:VpcConfig}") or []:
        if function["Name"] in FUNCTIONS:
            add("lambda", function["Name"])
    for api in read("apigatewayv2", "get-apis", query="Items[].{Id:ApiId,Name:Name,Tags:Tags}") or []:
        if api["Name"] in APIS and api.get("Tags", {}).get("Project") == PROJECT:
            add("api", api["Id"], name=api["Name"])
        elif api["Name"] in APIS:
            report["errors"].append("API ownership tags are missing or unexpected: " + api["Id"])
    for link in read("apigatewayv2", "get-vpc-links", query="Items") or []:
        if link["Name"] == "fiap-shared-api" and link.get("Tags", {}).get("Project") == PROJECT:
            add("vpc-link", link["VpcLinkId"])
    for secret in read("secretsmanager", "list-secrets", "--include-planned-deletion",
                       query="SecretList[].{Name:Name,Arn:ARN,Deleted:DeletedDate,Tags:Tags}") or []:
        if secret["Name"].startswith("fiap/") and owned(secret.get("Tags")):
            if secret.get("Deleted"):
                report["free_resources"].append({"kind": "secret", "id": secret["Arn"], "state": "ScheduledDeletion", "reason": "AWS não cobra segredos marcados para exclusão."})
            else:
                add("secret", secret["Arn"], name=secret["Name"])
    for alias in read("kms", "list-aliases", query="Aliases") or []:
        if alias["AliasName"].startswith("alias/aws/"):
            report["free_resources"].append({"kind": "aws-managed-kms", "id": alias["AliasName"], "state": "Retained", "reason": "Sem tarifa de criação/armazenamento da chave gerenciada pela AWS; chamadas criptográficas ainda podem gerar uso."})
        if alias["AliasName"] == "alias/fiap-shared-eks":
            key = read("kms", "describe-key", "--key-id", alias["TargetKeyId"], query="KeyMetadata")
            if key and key["KeyManager"] == "CUSTOMER":
                if key["KeyState"] == "PendingDeletion":
                    report["free_resources"].append({"kind": "kms", "id": key["KeyId"], "state": "PendingDeletion", "reason": "AWS não cobra a chave durante a espera de exclusão; cancelamento pode restabelecer cobrança."})
                else:
                    add("kms", key["KeyId"], state=key["KeyState"])
    for repository in read("ecr", "describe-repositories", query="repositories") or []:
        if repository["repositoryName"] == "fiap-application":
            add("ecr", repository["repositoryName"])
    names = read("s3api", "list-buckets", query="Buckets[].Name") or []
    if BUCKET in names:
        add("bucket", BUCKET)
    for group in read("logs", "describe-log-groups", query="logGroups[].{Name:logGroupName,Bytes:storedBytes}") or []:
        if group["Name"] in LOG_GROUPS:
            add("logs", group["Name"], bytes=group["Bytes"])
    for project in read("codebuild", "list-projects", query="projects") or []:
        if project in BUILDS:
            add("codebuild", project)
    for rule in read("events", "list-rules", "--name-prefix", "fiap-uptime", query="Rules") or []:
        if rule["Name"] == "fiap-uptime-every-five-minutes":
            add("rule", rule["Name"], state=rule["State"])
    roles = read("iam", "list-roles", query="Roles[].RoleName") or []
    for role in roles:
        if role.startswith("fiap-"):
            report["free_resources"].append({"kind": "iam", "id": role, "state": "Retained", "reason": "Sem tarifa direta de provisionamento; não executa recursos sozinho."})
    providers = read("iam", "list-open-id-connect-providers", query="OpenIDConnectProviderList[].Arn") or []
    for provider in providers:
        if provider.endswith("/token.actions.githubusercontent.com"):
            report["free_resources"].append({"kind": "oidc", "id": provider, "state": "Retained", "reason": "Sem tarifa direta de provisionamento."})
    for identity in read("sesv2", "list-email-identities", query="EmailIdentities[].IdentityName") or []:
        metadata = read("sesv2", "get-email-identity", "--email-identity", identity) or {}
        if owned(metadata.get("Tags")):
            report["free_resources"].append({"kind": "ses-identity", "id": identity, "state": "Retained",
                "reason": "Identidade de remetente sem envio agendado; sua retenção não executa mensagens nem gera tarifa de armazenamento."})
    identifiers = {item["id"] for item in report["resources"] + report["free_resources"]}
    for item in report["resources"]:
        identifiers.update(item.get("children", []))
    regions = read("ec2", "describe-regions", "--all-regions", query="Regions[?OptInStatus!='not-opted-in'].RegionName") or []
    report["tag_audit_regions"] = regions
    for region in regions:
        arns = read("resourcegroupstaggingapi", "get-resources", "--tag-filters", "Key=Project,Values=" + PROJECT,
                    query="ResourceTagMappingList[].ResourceARN", region=region) or []
        for arn in arns:
            service, value = arn.split(":", 5)[2], arn.split(":", 5)[5]
            if service == "iam" and value.startswith(("role/fiap-", "policy/fiap-", "oidc-provider/token.actions.githubusercontent.com")):
                continue
            if region != REGION:
                report["errors"].append("Project resource outside approved region: " + arn)
                continue
            candidates = {arn, value, value.split("/", 1)[-1], value.split(":", 1)[-1].removesuffix(":*")}
            handled = covered_identifier(service, candidates, report)
            if service == "apigateway":
                parts = value.strip("/").split("/")
                if len(parts) >= 2 and parts[0] in {"apis", "vpclinks"} and covered_identifier(service, {parts[1]}, report):
                    handled = True
            if service == "ec2" and value.startswith("security-group-rule/") and not handled:
                rule_id = value.split("/", 1)[1]
                errors_before = len(report["errors"])
                rule = read("ec2", "describe-security-group-rules", "--security-group-rule-ids", rule_id,
                            query="SecurityGroupRules", missing=True)
                if len(report["errors"]) == errors_before and not rule:
                    handled = True
                    report["free_resources"].append({"kind": "verified-absent-security-group-rule", "id": rule_id,
                        "state": "Absent", "reason": "Entrada de tags antiga; consulta autoritativa do EC2 não encontrou a regra."})
            if service == "ec2" and value.startswith("vpc-endpoint/") and not handled:
                endpoint_id = value.split("/", 1)[1]
                errors_before = len(report["errors"])
                endpoint = read("ec2", "describe-vpc-endpoints", "--vpc-endpoint-ids", endpoint_id, query="VpcEndpoints", missing=True)
                if len(report["errors"]) == errors_before and (endpoint is None or all(item["State"] == "deleted" for item in endpoint)):
                    handled = True
                    report["free_resources"].append({"kind": "verified-absent-endpoint", "id": endpoint_id, "state": "Absent", "reason": "Entrada de tags antiga; consulta autoritativa não encontrou endpoint em operação."})
            if service == "eks" and value.startswith(("nodegroup/fiap-shared/", "addon/fiap-shared/", "access-entry/fiap-shared/", "podidentityassociation/fiap-shared/")) and any(item["kind"] == "eks" for item in report["resources"]):
                handled = True
            if service == "iam" and value.startswith(("role/fiap-", "policy/fiap-")):
                handled = True
            if not handled:
                report["errors"].append("Tagged resource not covered by the teardown engine: " + arn)
    report["confirmed_absences"] = []
    if not report["errors"]:
        for kind, label in (("eks", "EKS fiap-shared"), ("rds", "RDS fiap-shared-postgres"),
                            ("alb", "ALB fiap-shared-api"), ("nat", "NAT do projeto"),
                            ("ec2", "EC2 do projeto em execução"), ("volume", "Volumes EBS identificados como do projeto"),
                            ("eip", "Elastic IPs identificados como do projeto")):
            if not any(item["kind"] == kind for item in report["resources"]):
                report["confirmed_absences"].append({"kind": kind, "label": label})
    return report


def cost_report(start, client=None):
    aws = client or Aws()
    end = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)).isoformat()
    result = {"available": False, "start": start, "end_exclusive": end, "currency": "USD",
              "attribution": "Conta TWM por serviço; não representa custo individual comprovado de cada recurso.",
              "services": [], "estimated": True}
    try:
        usage = aws.run("ce", "get-cost-and-usage", "--time-period", f"Start={start},End={end}",
            "--granularity", "DAILY", "--metrics", "UnblendedCost", "--group-by", "Type=DIMENSION,Key=SERVICE", "Type=DIMENSION,Key=RECORD_TYPE",
            "--filter", json.dumps({"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [ACCOUNT]}}), region="us-east-1")
        amounts, estimated, records = {}, False, []
        for period in usage["ResultsByTime"]:
            estimated |= period.get("Estimated", False)
            for group in period["Groups"]:
                name, record_type = group["Keys"]
                amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])
                row = amounts.setdefault(name, {"consumption": Decimal(0), "credits": Decimal(0), "refunds": Decimal(0), "amount": Decimal(0)})
                row["amount"] += amount
                category = "credits" if record_type == "Credit" else "refunds" if record_type == "Refund" else "consumption"
                row[category] += amount
                records.append({"date": period["TimePeriod"]["Start"], "service": name,
                                "record_type": record_type, "amount": str(amount), "unit": group["Metrics"]["UnblendedCost"]["Unit"]})
        result.update(available=True, estimated=estimated,
            total=str(sum((row["amount"] for row in amounts.values()), Decimal(0))),
            consumption=str(sum((row["consumption"] for row in amounts.values()), Decimal(0))),
            credits=str(sum((row["credits"] for row in amounts.values()), Decimal(0))),
            refunds=str(sum((row["refunds"] for row in amounts.values()), Decimal(0))), records=records,
            services=[{"service": name, **{key: str(value) for key, value in row.items()}} for name, row in sorted(amounts.items())])
    except Exception as error:
        result["error"] = str(error)
    return result


def purge_bucket(aws, name):
    # Re-list the first page after each deletion, including noncurrent versions.
    for _ in range(10000):
        page = aws.run("s3api", "list-object-versions", "--bucket", name, "--no-paginate") or {}
        objects = [{"Key": item["Key"], "VersionId": item["VersionId"]}
                   for key in ("Versions", "DeleteMarkers") for item in page.get(key, [])]
        if not objects:
            break
        for offset in range(0, len(objects), 1000):
            response = aws.change("s3api", "delete-objects", "--bucket", name,
                                 "--delete", json.dumps({"Objects": objects[offset:offset + 1000], "Quiet": True}))
            if response and response.get("Errors"):
                raise RuntimeError("S3 versions could not be removed")
    else:
        raise RuntimeError("S3 version deletion did not converge")
    uploads = aws.run("s3api", "list-multipart-uploads", "--bucket", name) or {}
    for upload in uploads.get("Uploads", []):
        aws.change("s3api", "abort-multipart-upload", "--bucket", name, "--key", upload["Key"], "--upload-id", upload["UploadId"])
    aws.change("s3api", "delete-bucket", "--bucket", name)


def wait_until_empty(read, description, timeout=1800):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not read():
            return
        time.sleep(15)
    raise RuntimeError("Timed out waiting for " + description)


def destroy(before, actions, directory, client=None):
    aws = client or Aws(destructive=True)
    aws.identity()
    resources = before["resources"]
    if before["errors"]:
        raise ValueError("Cannot destroy from an incomplete inventory")

    def items(kind):
        return [item for item in resources if item["kind"] == kind]

    def change(item, service, operation, *arguments, **kwargs):
        if operation.startswith("delete-"):
            kwargs.setdefault("missing", True)
        result = aws.change(service, operation, *arguments, **kwargs)
        actions.append({"kind": item["kind"], "id": item["id"], "operation": operation, "requested": True})
        (directory / "actions.json").write_text(json.dumps(actions, indent=2), encoding="utf-8")
        print(f"Requested {operation}: {item['id']}", flush=True)
        return result

    for item in items("rule"):
        change(item, "events", "disable-rule", "--name", item["id"])
        targets = aws.run("events", "list-targets-by-rule", "--rule", item["id"], query="Targets[].Id") or []
        if targets:
            result = change(item, "events", "remove-targets", "--rule", item["id"], "--ids", *targets)
            if result.get("FailedEntryCount"):
                raise RuntimeError("EventBridge targets could not be removed")
        change(item, "events", "delete-rule", "--name", item["id"])
    for item in items("api"):
        change(item, "apigatewayv2", "delete-api", "--api-id", item["id"])
    for item in items("vpc-link"):
        change(item, "apigatewayv2", "delete-vpc-link", "--vpc-link-id", item["id"])
    for item in items("lambda"):
        change(item, "lambda", "delete-function", "--function-name", item["id"])
    # Remove compute first when private Kubernetes cannot be reached. With all
    # nodes gone, the LB controller cannot recreate AWS load balancers.
    for item in items("eks"):
        profiles = aws.run("eks", "list-fargate-profiles", "--cluster-name", CLUSTER, query="fargateProfileNames") or []
        if profiles:
            raise RuntimeError("Unexpected Fargate profiles require an expanded reviewed plan")
        nodegroups = aws.run("eks", "list-nodegroups", "--cluster-name", CLUSTER, query="nodegroups") or []
        for name in nodegroups:
            change(item, "eks", "delete-nodegroup", "--cluster-name", CLUSTER, "--nodegroup-name", name)
        wait_until_empty(lambda: aws.run("eks", "list-nodegroups", "--cluster-name", CLUSTER, query="nodegroups"), "EKS nodegroups")
        if item.get("deletion_protection"):
            update = change(item, "eks", "update-cluster-config", "--name", CLUSTER, "--no-deletion-protection")
            wait_until_empty(lambda: aws.run("eks", "describe-update", "--name", CLUSTER, "--update-id", update["update"]["id"], query="update.status") == "InProgress", "EKS update")
        change(item, "eks", "delete-cluster", "--name", CLUSTER)
        wait_until_empty(lambda: aws.run("eks", "describe-cluster", "--name", CLUSTER, missing=True), "EKS deletion")
    for item in items("asg"):
        present = aws.run("autoscaling", "describe-auto-scaling-groups", "--auto-scaling-group-names", item["id"], query="AutoScalingGroups")
        if present:
            change(item, "autoscaling", "delete-auto-scaling-group", "--auto-scaling-group-name", item["id"], "--force-delete")
            wait_until_empty(lambda: aws.run("autoscaling", "describe-auto-scaling-groups", "--auto-scaling-group-names", item["id"], query="AutoScalingGroups"), "Auto Scaling deletion")
    for item in items("ec2"):
        # Nodegroup removal normally terminates these; terminate only still-live IDs from the approved plan.
        state = aws.run("ec2", "describe-instances", "--instance-ids", item["id"], query="Reservations[].Instances[].State.Name") or []
        if any(value not in {"terminated", "shutting-down"} for value in state):
            change(item, "ec2", "terminate-instances", "--instance-ids", item["id"])
        wait_until_empty(lambda: [s for s in aws.run("ec2", "describe-instances", "--instance-ids", item["id"], query="Reservations[].Instances[].State.Name") or [] if s != "terminated"], "EC2 termination")
    for item in items("alb"):
        change(item, "elbv2", "delete-load-balancer", "--load-balancer-arn", item["id"])
        wait_until_empty(lambda: aws.run("elbv2", "describe-load-balancers", "--load-balancer-arns", item["id"], missing=True), "ALB deletion")
    for item in items("target-group"):
        change(item, "elbv2", "delete-target-group", "--target-group-arn", item["id"])
    for item in items("rds"):
        if item.get("protection"):
            change(item, "rds", "modify-db-instance", "--db-instance-identifier", item["id"], "--no-deletion-protection", "--apply-immediately")
            wait_until_empty(lambda: aws.run("rds", "describe-db-instances", "--db-instance-identifier", item["id"], query="DBInstances[0].DeletionProtection"), "RDS protection update", timeout=300)
        if item.get("status") != "deleting":
            change(item, "rds", "delete-db-instance", "--db-instance-identifier", item["id"], "--skip-final-snapshot", "--delete-automated-backups")
        wait_until_empty(lambda: aws.run("rds", "describe-db-instances", "--db-instance-identifier", item["id"], missing=True), "RDS deletion", timeout=3600)
    for item in items("rds-snapshot"):
        change(item, "rds", "delete-db-snapshot", "--db-snapshot-identifier", item["id"])
    for item in items("rds-backup"):
        change(item, "rds", "delete-db-instance-automated-backup", "--dbi-resource-id", item["id"])
    for item in items("rds-subnet-group"):
        change(item, "rds", "delete-db-subnet-group", "--db-subnet-group-name", item["id"])
    for kind, service, operation, argument in (
        ("volume", "ec2", "delete-volume", "--volume-id"),
        ("ebs-snapshot", "ec2", "delete-snapshot", "--snapshot-id"),
        ("codebuild", "codebuild", "delete-project", "--name"),
        ("logs", "logs", "delete-log-group", "--log-group-name"),
    ):
        for item in items(kind):
            change(item, service, operation, argument, item["id"], missing=True)
    for item in items("secret"):
        change(item, "secretsmanager", "delete-secret", "--secret-id", item["id"], "--recovery-window-in-days", "7")
    for item in items("kms"):
        if item["state"] != "PendingDeletion":
            change(item, "kms", "schedule-key-deletion", "--key-id", item["id"], "--pending-window-in-days", "7")
    for item in items("ecr"):
        change(item, "ecr", "delete-repository", "--repository-name", item["id"], "--force")
    for item in items("endpoint"):
        result = change(item, "ec2", "delete-vpc-endpoints", "--vpc-endpoint-ids", item["id"])
        if result.get("Unsuccessful"):
            raise RuntimeError("VPC endpoint deletion failed")
    for item in items("nat"):
        change(item, "ec2", "delete-nat-gateway", "--nat-gateway-id", item["id"])
        wait_until_empty(lambda: [n for n in aws.run("ec2", "describe-nat-gateways", "--nat-gateway-ids", item["id"], query="NatGateways") or [] if n["State"] != "deleted"], "NAT deletion")
    for item in items("eip"):
        change(item, "ec2", "release-address", "--allocation-id", item["id"])
    for item in items("vpc"):
        clean_network(aws, item, change)
    # Backend last: GitHub variables remain destroyed; normal deploys also fail
    # closed when this bucket is absent. No state content is emitted to reports.
    for item in items("bucket"):
        purge_bucket(aws, item["id"])
        actions.append({"kind": "bucket", "id": item["id"], "operation": "delete-bucket", "requested": True})


def clean_network(aws, vpc, change):
    identifier = vpc["id"]
    filters = ("--filters", "Name=vpc-id,Values=" + identifier)
    wait_until_empty(lambda: aws.run("ec2", "describe-network-interfaces", *filters, query="NetworkInterfaces"), "service-owned ENIs", timeout=2700)
    groups = aws.run("ec2", "describe-security-groups", *filters, query="SecurityGroups") or []
    identifiers = {group["GroupId"] for group in groups}
    for group in groups:
        for field, direction in (("IpPermissions", "ingress"), ("IpPermissionsEgress", "egress")):
            for permission in group[field]:
                pairs = [pair for pair in permission.get("UserIdGroupPairs", []) if pair["GroupId"] in identifiers]
                if pairs:
                    value = {key: permission[key] for key in ("IpProtocol", "FromPort", "ToPort") if key in permission}
                    value["UserIdGroupPairs"] = pairs
                    change(vpc, "ec2", "revoke-security-group-" + direction, "--group-id", group["GroupId"], "--ip-permissions", json.dumps([value]))
    for group in groups:
        if group["GroupName"] != "default":
            change(vpc, "ec2", "delete-security-group", "--group-id", group["GroupId"])
    for table in aws.run("ec2", "describe-route-tables", *filters, query="RouteTables") or []:
        if any(association.get("Main") for association in table["Associations"]):
            continue
        for association in table["Associations"]:
            change(vpc, "ec2", "disassociate-route-table", "--association-id", association["RouteTableAssociationId"])
        change(vpc, "ec2", "delete-route-table", "--route-table-id", table["RouteTableId"])
    for subnet in aws.run("ec2", "describe-subnets", *filters, query="Subnets") or []:
        change(vpc, "ec2", "delete-subnet", "--subnet-id", subnet["SubnetId"])
    for gateway in aws.run("ec2", "describe-internet-gateways", "--filters", "Name=attachment.vpc-id,Values=" + identifier, query="InternetGateways") or []:
        change(vpc, "ec2", "detach-internet-gateway", "--internet-gateway-id", gateway["InternetGatewayId"], "--vpc-id", identifier)
        change(vpc, "ec2", "delete-internet-gateway", "--internet-gateway-id", gateway["InternetGatewayId"])
    change(vpc, "ec2", "delete-vpc", "--vpc-id", identifier)
