"""PR operations for the shared AWS teardown. Execution requires a reviewed ALL merge."""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

ORG = "FIAP-GRUPO05"
REPOS = ("fiap-k8s", "fiap-database", "fiap-lambda", "fiap-application")
TEAM = {"codewesleylima", "timbeck97", "matpitas"}
SOURCE = "feature/destroy-infra-aws"
TARGET = "ALL"
REQUEST = ".github/operations/destroy-request.json"
ACCOUNT = "456687462806"
RELEASE = re.compile(r"release/v(\d+)\.(\d+)\.(\d+)")


def api(method, path, body=None, *, raw=False):
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request("https://api.github.com/" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"}, method=method)
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, newurl):
            if urllib.parse.urlparse(newurl).scheme != "https":
                raise ValueError("Non-HTTPS API redirect rejected")
            redirected = super().redirect_request(request, response, code, message, headers, newurl)
            if urllib.parse.urlparse(request.full_url).netloc != urllib.parse.urlparse(newurl).netloc:
                redirected.remove_header("Authorization")
            return redirected
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=60) as response:
        payload = response.read()
        return payload if raw else json.loads(payload) if payload else None


def pages(path):
    result, page = [], 1
    while True:
        items = api("GET", path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
        if not isinstance(items, list):
            raise RuntimeError("Expected a paginated list")
        result.extend(items)
        if len(items) < 100:
            return result
        page += 1


def repo_path(repo):
    if repo not in REPOS:
        raise ValueError("Unknown project repository")
    return f"repos/{ORG}/{repo}"


def ref(repo, branch):
    return api("GET", repo_path(repo) + "/git/ref/heads/" + urllib.parse.quote(branch, safe=""))["object"]["sha"]


def content(repo, path, revision):
    return json.loads(api("GET", repo_path(repo) + "/contents/" + path + "?ref=" + revision,
                          raw=True).decode())


def read_request(revision):
    import base64
    response = content("fiap-k8s", REQUEST, revision)
    return json.loads(base64.b64decode(response["content"]))


def validate_request(document):
    allowed = {"schema", "request_id", "requested_by", "account", "region", "confirmation",
               "delete_project_data", "implementation_sha", "billing_start", "repositories"}
    if set(document) != allowed or document["schema"] != 1:
        raise ValueError("Request schema is not supported")
    uuid.UUID(document["request_id"])
    if document["requested_by"] not in TEAM or document["account"] != ACCOUNT or document["region"] != "sa-east-1":
        raise ValueError("Unexpected requester, account or region")
    if document["confirmation"] != "DESTRUIR-" + ACCOUNT or document["delete_project_data"] is not True:
        raise ValueError("Explicit acknowledgment of project data deletion is required")
    if not re.fullmatch(r"[0-9a-f]{40}", document["implementation_sha"]):
        raise ValueError("Trusted implementation SHA required")
    beginning = dt.date.fromisoformat(document["billing_start"])
    if beginning > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("Billing start cannot be in the future")
    if set(document["repositories"]) != set(REPOS):
        raise ValueError("All four repository snapshots are required")
    for repo, snapshot in document["repositories"].items():
        release = snapshot.get("release")
        if not isinstance(release, str) or not RELEASE.fullmatch(release):
            raise ValueError("Release branch must be explicit")
        if set(snapshot) != {"release", "refs"} or set(snapshot["refs"]) != {"develop", release, "prod", "main"}:
            raise ValueError("Unexpected branch snapshot")
        if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in snapshot["refs"].values()):
            raise ValueError("Invalid branch SHA")
    return document


def validate_pr(number, require_merged=False):
    pr = api("GET", repo_path("fiap-k8s") + f"/pulls/{number}")
    if pr["head"]["ref"] != SOURCE or pr["base"]["ref"] != TARGET or pr["head"]["repo"]["full_name"] != f"{ORG}/fiap-k8s":
        raise ValueError("Only the exact operational branch in this repository can target ALL")
    files = pages(repo_path("fiap-k8s") + f"/pulls/{number}/files")
    if len(files) != 1 or files[0]["filename"] != REQUEST or files[0]["status"] not in {"added", "modified"}:
        raise ValueError("The operational PR may change only " + REQUEST)
    document = validate_request(read_request(pr["head"]["sha"]))
    runs = api("GET", repo_path("fiap-k8s") + "/actions/workflows/pipeline.yml/runs?event=push&head_sha=" + pr["head"]["sha"])["workflow_runs"]
    if not any(run["head_branch"] == SOURCE and run["actor"]["login"] == document["requested_by"] for run in runs):
        raise ValueError("No authenticated push by the declared requester was found")
    if document["implementation_sha"] != ref("fiap-k8s", "main"):
        raise ValueError("Main changed: prepare and review a fresh request")
    if require_merged and not pr.get("merged"):
        raise ValueError("An approved PR merged into ALL is required")
    return pr, document


def approvals(pr, document, reviews):
    latest = {}
    for review in reviews:
        # Comments do not revoke an approval; changes requested do.
        if review["state"] != "COMMENTED":
            latest[review["user"]["login"]] = review
    required = TEAM - {document["requested_by"]}
    accepted = {login for login, review in latest.items() if login in required
                and review["state"] == "APPROVED" and review.get("commit_id") == pr["head"]["sha"]}
    if accepted != required:
        raise ValueError("Approvals required for the current commit: " + ", ".join(sorted(required - accepted)))
    return sorted(accepted)


def check_approvals(pr, document):
    return approvals(pr, document, pages(repo_path("fiap-k8s") + f"/pulls/{pr['number']}/reviews"))


def snapshot_valid(document):
    for repo, snapshot in document["repositories"].items():
        for branch, expected in snapshot["refs"].items():
            if ref(repo, branch) != expected:
                raise ValueError(f"{repo}/{branch} changed after the request; review a fresh snapshot")


def installation_ready(document):
    import base64
    expected = (Path(__file__).parent / "infra_guard.py").read_bytes().replace(b"\r\n", b"\n")
    expected_sha = hashlib.sha1(b"blob " + str(len(expected)).encode() + b"\0" + expected).hexdigest()
    for repo, snapshot in document["repositories"].items():
        for branch, revision in snapshot["refs"].items():
            guard = content(repo, ".github/scripts/infra_guard.py", revision)
            workflow = content(repo, ".github/workflows/pipeline.yml", revision)
            text = base64.b64decode(workflow["content"]).decode()
            if guard["sha"] != expected_sha or "FIAP_INFRA_STATE" not in text or "python .github/scripts/infra_guard.py" not in text:
                raise ValueError(f"Install the reviewed publication guard on {repo}/{branch} before requesting destroy")


def prepare():
    actor = api("GET", "user")["login"]
    if actor not in TEAM:
        raise ValueError("Requester must be a project member")
    document = {"schema": 1, "request_id": str(uuid.uuid4()), "requested_by": actor,
                "account": ACCOUNT, "region": "sa-east-1", "confirmation": "DESTRUIR-" + ACCOUNT,
                "delete_project_data": True, "implementation_sha": ref("fiap-k8s", "main"),
                "billing_start": dt.date.today().replace(day=1).isoformat(), "repositories": {}}
    for repo in REPOS:
        branches = pages(repo_path(repo) + "/branches")
        releases = [b["name"] for b in branches if RELEASE.fullmatch(b["name"])]
        if not releases:
            raise ValueError("Missing release in " + repo)
        release = max(releases, key=lambda name: tuple(map(int, RELEASE.fullmatch(name).groups())))
        document["repositories"][repo] = {"release": release,
            "refs": {branch: ref(repo, branch) for branch in ("develop", release, "prod", "main")}}
    validate_request(document)
    installation_ready(document)
    path = Path(REQUEST)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print("Request prepared. Commit only " + REQUEST + " on " + SOURCE + " based on origin/ALL.")


def propose():
    if os.environ.get("GITHUB_REF_NAME") != SOURCE:
        raise ValueError("Unexpected branch")
    sha = os.environ["GITHUB_SHA"]
    document = validate_request(read_request(sha))
    if document["requested_by"] != os.environ["GITHUB_ACTOR"]:
        raise ValueError("Only the recorded requester may push this request")
    comparison = api("GET", repo_path("fiap-k8s") + "/compare/ALL..." + sha)
    if [f["filename"] for f in comparison.get("files", [])] != [REQUEST]:
        raise ValueError("Branch must start at ALL and change only the request")
    if document["implementation_sha"] != ref("fiap-k8s", "main"):
        raise ValueError("Request implementation SHA is stale")
    snapshot_valid(document)
    installation_ready(document)
    existing = api("GET", repo_path("fiap-k8s") + "/pulls?state=open&base=ALL&head=" + ORG + ":" + SOURCE)
    body = "\n".join([
        "Solicita a desmontagem real da infraestrutura AWS compartilhada dos quatro projetos.",
        "Objetivo: encerrar recursos e custos recorrentes na conta TWM 456687462806, região sa-east-1.",
        "Aprovação: os dois integrantes diferentes do solicitante, no commit atual do PR.",
        "Após o merge em ALL, bloqueia deploys e sincroniza develop → release ativa → prod → main sem force push.",
        "Exclui recursos e dados do projeto conforme o inventário aprovado; estados, imagens, logs e backups entram no escopo.",
        "A auditoria final distingue removido, sem cobrança direta, pendente e não comprovado.",
        "Custos reais dependem dos dados de faturamento; indisponibilidade não será apresentada como custo zero.",
        "O relatório final ficará no resumo e nos artefatos da execução do GitHub Actions.",
        f"Solicitante: {document['requested_by']}. Pedido: {document['request_id']}.",
    ])
    pr = existing[0] if existing else api("POST", repo_path("fiap-k8s") + "/pulls",
        {"head": SOURCE, "base": TARGET, "title": "feat(ops): solicitar destroy da infraestrutura AWS", "body": body})
    api("POST", repo_path("fiap-k8s") + f"/pulls/{pr['number']}/requested_reviewers",
        {"reviewers": sorted(TEAM - {document["requested_by"]})})
    print(pr["html_url"])


def plan(number, directory):
    from aws_destroy import inventory, cost_report
    pr, document = validate_pr(number)
    snapshot_valid(document)
    installation_ready(document)
    name = "destroy-plan-" + pr["head"]["sha"]
    artifacts = api("GET", repo_path("fiap-k8s") + "/actions/artifacts?name=" + name)["artifacts"]
    available = any(not artifact["expired"] for artifact in artifacts)
    if available:
        result = approved_plan(pr, directory)
        current = inventory()
        if current["errors"] or resource_keys(current) - resource_keys(result["inventory"]):
            raise ValueError("Inventory expanded after the original plan; submit a fresh request")
    else:
        if os.environ.get("GITHUB_EVENT_NAME") == "pull_request_review":
            raise ValueError("An original plan must exist before approval")
        result = {"head_sha": pr["head"]["sha"], "request": document, "inventory": inventory(),
                  "costs": cost_report(document["billing_start"])}
    if result["inventory"]["errors"]:
        raise RuntimeError("Inventory incomplete; inspect read permissions")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Plan prepared. Deletes project data and all discovered scoped resources; does not delete IAM or unrelated resources.")


def frozen(state):
    for repo in REPOS:
        path = repo_path(repo) + "/actions/variables/FIAP_INFRA_STATE"
        try:
            api("PATCH", path, {"name": "FIAP_INFRA_STATE", "value": state})
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            api("POST", repo_path(repo) + "/actions/variables", {"name": "FIAP_INFRA_STATE", "value": state})
        if api("GET", path)["value"] != state:
            raise RuntimeError("Cannot verify publication freeze")


def cancel_other_runs():
    own = int(os.environ["GITHUB_RUN_ID"])
    for repo in REPOS:
        for status in ("queued", "in_progress", "waiting", "pending"):
            runs = api("GET", repo_path(repo) + f"/actions/workflows/pipeline.yml/runs?status={status}&per_page=100")["workflow_runs"]
            if len(runs) == 100:
                raise RuntimeError("Too many active runs to freeze safely")
            for run in runs:
                if repo == "fiap-k8s" and run["id"] == own:
                    continue
                api("POST", repo_path(repo) + f"/actions/runs/{run['id']}/cancel")
                for _ in range(60):
                    if api("GET", repo_path(repo) + f"/actions/runs/{run['id']}")["status"] == "completed":
                        break
                    time.sleep(2)
                else:
                    raise RuntimeError("A publication run did not stop")


def synchronize(document, all_sha, log, directory):
    expected = {repo: dict(snapshot["refs"]) for repo, snapshot in document["repositories"].items()}
    for phase in ("develop", "release", "prod", "main"):
        for repo in REPOS:
            release = document["repositories"][repo]["release"]
            target = release if phase == "release" else phase
            source = (all_sha if repo == "fiap-k8s" else document["repositories"][repo]["refs"]["main"]) if phase == "develop" else expected[repo][{"release": "develop", "prod": release, "main": "prod"}[phase]]
            if ref(repo, target) != expected[repo][target]:
                raise ValueError(f"Concurrent change detected in {repo}/{target}")
            temporary = f"ops/sync-{document['request_id']}-{phase}"
            api("POST", repo_path(repo) + "/git/refs", {"ref": "refs/heads/" + temporary, "sha": expected[repo][target]})
            try:
                api("POST", repo_path(repo) + "/merges", {"base": temporary, "head": source,
                    "commit_message": f"chore(ops): sincronizar {target} para destroy {document['request_id']}"})
                merged = ref(repo, temporary)
                if ref(repo, target) != expected[repo][target]:
                    raise ValueError("Branch changed while preparing the merge")
                # A normal fast-forward update of a prepared merge commit. If
                # the target advanced concurrently, GitHub rejects non-FF.
                api("PATCH", repo_path(repo) + "/git/refs/heads/" + urllib.parse.quote(target, safe=""),
                    {"sha": merged, "force": False})
                if ref(repo, target) != merged:
                    raise ValueError("Cannot confirm synchronized branch")
                expected[repo][target] = merged
                log.append({"repository": repo, "branch": target, "sha": merged})
                (directory / "sync.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
            finally:
                api("DELETE", repo_path(repo) + "/git/refs/heads/" + urllib.parse.quote(temporary, safe=""))
    return log


def approved_plan(pr, directory):
    name = "destroy-plan-" + pr["head"]["sha"]
    artifacts = api("GET", repo_path("fiap-k8s") + "/actions/artifacts?name=" + name)["artifacts"]
    artifacts = [a for a in artifacts if not a["expired"]]
    if not artifacts:
        raise ValueError("Missing plan artifact for the approved request")
    blob = api("GET", repo_path("fiap-k8s") + f"/actions/artifacts/{artifacts[0]['id']}/zip", raw=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        document = json.loads(archive.read("plan.json"))
    if document["head_sha"] != pr["head"]["sha"]:
        raise ValueError("Plan SHA mismatch")
    return document


def execute(directory):
    from aws_destroy import Aws, inventory, destroy, cost_report, resource_keys
    directory.mkdir(parents=True, exist_ok=True)
    record = {"status": "blocked", "account": ACCOUNT, "sync": [], "actions": [], "errors": []}
    try:
        if os.environ.get("GITHUB_REF_NAME") != TARGET or os.environ.get("GITHUB_EVENT_NAME") != "push":
            raise ValueError("Destroy requires a push resulting from a reviewed ALL merge")
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        if event.get("created") or event.get("deleted") or event.get("forced"):
            raise ValueError("Branch creation, deletion or force push cannot destroy")
        sha = event["after"]
        if ref("fiap-k8s", TARGET) != sha:
            raise ValueError("A newer ALL request exists; stale execution rejected")
        candidates = api("GET", repo_path("fiap-k8s") + f"/commits/{sha}/pulls")
        candidates = [p for p in candidates if p.get("merged_at") and p["base"]["ref"] == TARGET and p.get("merge_commit_sha") == sha]
        if len(candidates) != 1:
            raise ValueError("Exactly one merged operational PR must identify the commit")
        pr, document = validate_pr(candidates[0]["number"], require_merged=True)
        record["approvals"] = check_approvals(pr, document)
        record["request"] = document
        snapshot_valid(document)
        installation_ready(document)
        plan_document = approved_plan(pr, directory)
        if plan_document["request"] != document:
            raise ValueError("Approved plan differs from the request")
        before = inventory()
        if before["errors"] or resource_keys(before) - resource_keys(plan_document["inventory"]):
            raise ValueError("New or unreadable resources require a fresh reviewed plan")
        record["before"] = before
        os.environ["FIAP_APPROVED_DESTROY_REQUEST"] = document["request_id"]
        destructive = Aws(destructive=True)
        frozen("destroying")
        destructive.control_state("destroying")
        cancel_other_runs()
        destructive.stop_builds()
        snapshot_valid(document)
        synchronize(document, sha, record["sync"], directory)
        record["status"] = "destroying"
        (directory / "execution.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        destroy(before, record["actions"], directory)
        record["status"] = "destroyed"
        frozen("destroyed")
    except Exception as error:
        record["errors"].append(str(error))
        record["status"] = "partial" if record["actions"] else "blocked"
    finally:
        try:
            record["after"] = inventory()
            start = record.get("request", {}).get("billing_start", dt.date.today().replace(day=1).isoformat())
            record["costs"] = cost_report(start)
        except Exception as error:
            record["errors"].append("Final audit incomplete: " + str(error))
        (directory / "execution.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if record["status"] != "destroyed" or record.get("after", {}).get("resources") or record.get("after", {}).get("errors"):
        raise SystemExit("Destruction is blocked, incomplete or has residual resources; see report")
    if not record.get("costs", {}).get("available"):
        raise SystemExit("Resources removed; billing verification is pending. See report; no zero-cost claim is made.")


def audit(directory, after_execution=False):
    from aws_destroy import inventory, cost_report
    current = inventory()
    directory.mkdir(parents=True, exist_ok=True)
    record = {"status": "audit-only", "before": current, "after": current,
              "costs": cost_report(dt.date.today().replace(day=1).isoformat()), "errors": [], "actions": [], "sync": []}
    if after_execution:
        record["status"] = "independent-final-audit"
        try:
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            candidates = api("GET", repo_path("fiap-k8s") + f"/commits/{event['after']}/pulls")
            candidates = [pr for pr in candidates if pr.get("merged_at") and pr["base"]["ref"] == TARGET and pr.get("merge_commit_sha") == event["after"]]
            if len(candidates) != 1:
                raise ValueError("Merged operational PR not identified")
            pr = api("GET", repo_path("fiap-k8s") + f"/pulls/{candidates[0]['number']}")
            plan_document = approved_plan(pr, directory)
            record["before"] = plan_document["inventory"]
            record["request"] = plan_document["request"]
            record["costs"] = cost_report(record["request"]["billing_start"])
            artifacts = api("GET", repo_path("fiap-k8s") + f"/actions/runs/{os.environ['GITHUB_RUN_ID']}/artifacts")["artifacts"]
            original_name = f"aws-destroy-report-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
            source = next((item for item in artifacts if item["name"] == original_name and not item["expired"]), None)
            if source:
                blob = api("GET", repo_path("fiap-k8s") + f"/actions/artifacts/{source['id']}/zip", raw=True)
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    previous = json.loads(archive.read("execution.json"))
                for field in ("actions", "sync", "approvals"):
                    record[field] = previous.get(field, [])
                record["execution_status"] = previous.get("status", "unknown")
                record["errors"] += previous.get("errors", [])
            else:
                record["errors"].append("Original runner did not publish its log; fresh AWS verification is shown independently")
        except Exception as error:
            record["errors"].append("Could not recover approved execution history: " + str(error))
    (directory / "execution.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if current["resources"] or current["errors"] or record["errors"] or not record["costs"]["available"]:
        raise SystemExit("Residual resources, incomplete audit or unavailable billing; see report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "propose", "validate", "approvals", "plan", "execute", "audit"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--directory", type=Path, default=Path("destroy-report"))
    parser.add_argument("--after-execution", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "propose":
        propose()
    elif args.command == "validate":
        pr, document = validate_pr(args.pr)
        snapshot_valid(document)
        print("Request is valid; this does not authorize deletion")
    elif args.command == "approvals":
        pr, document = validate_pr(args.pr)
        print("Approvals verified: " + ", ".join(check_approvals(pr, document)))
    elif args.command == "plan":
        plan(args.pr, args.directory)
    elif args.command == "execute":
        execute(args.directory)
    elif args.command == "audit":
        audit(args.directory, args.after_execution)
