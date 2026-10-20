"""Prepare/apply GitHub controls. No AWS deletion; apply is explicit."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ORG = "FIAP-GRUPO05"
REPOS = ("fiap-k8s", "fiap-database", "fiap-lambda", "fiap-application")


def gh(method, endpoint, body=None):
    command = ["gh", "api", "--method", method, endpoint]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def ruleset():
    return {"name": "protect-ALL-destroy", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/ALL"], "exclude": []}}, "bypass_actors": [],
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
                {"type": "pull_request", "parameters": {"required_approving_review_count": 2,
                    "dismiss_stale_reviews_on_push": True, "require_code_owner_review": False,
                    "require_last_push_approval": True, "required_review_thread_resolution": True}},
                {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": True,
                    "required_status_checks": [{"context": name, "integration_id": 15368}
                        for name in ("Route", "Destroy request", "Destroy approvals", "Destroy plan")]}}]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--operations-app-id", type=int)
    parser.add_argument("--operations-client-id")
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.freeze_only and (not args.operations_client_id or not args.operations_app_id or args.operations_app_id <= 0 or args.operations_app_id == 5352822):
        raise SystemExit("Use a dedicated operations App, not the promotion App")
    root = Path(__file__).resolve().parents[1]
    path = root / ".github/rulesets/protect-ALL.json"
    if not args.freeze_only:
        path.write_text(json.dumps(ruleset(), indent=2) + "\n", encoding="utf-8")
        print("Prepared " + str(path))
    if not args.apply:
        print("No remote changes. Apply only after reviewing the App scope and installation checklist.")
        raise SystemExit(0)
    central = f"repos/{ORG}/fiap-k8s"
    if args.freeze_only:
        for repo in REPOS:
            base = f"repos/{ORG}/{repo}/actions/variables"
            variables = gh("GET", base)["variables"]
            exists = any(item["name"] == "FIAP_INFRA_STATE" for item in variables)
            gh("PATCH" if exists else "POST", base + ("/FIAP_INFRA_STATE" if exists else ""),
               {"name": "FIAP_INFRA_STATE", "value": "destroyed"})
        print("Maintenance variables configured. Legacy workflows without the guard must not be used to publish.")
        raise SystemExit(0)
    # Never create ALL from a main that cannot validate the operational PR.
    gh("GET", central + "/contents/.github/scripts/destroy_ops.py?ref=main")
    # Provision ALL once, before protecting it. Do not reset an existing ALL.
    branches = gh("GET", central + "/branches?per_page=100")
    if not any(branch["name"] == "ALL" for branch in branches):
        main = gh("GET", central + "/git/ref/heads/main")["object"]["sha"]
        gh("POST", central + "/git/refs", {"ref": "refs/heads/ALL", "sha": main})
    environment = {"wait_timer": 0, "prevent_self_review": False, "reviewers": [],
                   "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
    gh("PUT", central + "/environments/aws-destroy", environment)
    policies = gh("GET", central + "/environments/aws-destroy/deployment-branch-policies")["branch_policies"]
    if any(policy["name"] != "ALL" for policy in policies):
        raise SystemExit("Unexpected environment branch policy; review manually instead of expanding access")
    if not policies:
        gh("POST", central + "/environments/aws-destroy/deployment-branch-policies", {"name": "ALL", "type": "branch"})
    variable_path = central + "/environments/aws-destroy/variables"
    existing_variables = gh("GET", variable_path)["variables"]
    exists = any(item["name"] == "FIAP_OPERATIONS_APP_CLIENT_ID" for item in existing_variables)
    gh("PATCH" if exists else "POST", variable_path + ("/FIAP_OPERATIONS_APP_CLIENT_ID" if exists else ""),
       {"name": "FIAP_OPERATIONS_APP_CLIENT_ID", "value": args.operations_client_id})
    for repo in REPOS:
        base = f"repos/{ORG}/{repo}"
        variables = gh("GET", base + "/actions/variables")["variables"]
        method = "PATCH" if any(item["name"] == "FIAP_INFRA_STATE" for item in variables) else "POST"
        gh(method, base + "/actions/variables" + ("/FIAP_INFRA_STATE" if method == "PATCH" else ""),
           {"name": "FIAP_INFRA_STATE", "value": "destroyed"})
        existing = gh("GET", base + "/rulesets")
        for item in existing:
            if item["name"] in {"protect-develop", "protect-release", "protect-prod", "protect-main"}:
                document = gh("GET", base + f"/rulesets/{item['id']}")
                document = {key: document[key] for key in ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")}
                if not any(actor["actor_type"] == "Integration" and actor["actor_id"] == args.operations_app_id for actor in document["bypass_actors"]):
                    document["bypass_actors"].append({"actor_type": "Integration", "actor_id": args.operations_app_id, "bypass_mode": "always"})
                gh("PUT", base + f"/rulesets/{item['id']}", document)
                (root / "docs" / f"destroy-ruleset-{repo}-{item['name']}.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
        if repo == "fiap-k8s":
            match = next((item for item in existing if item["name"] == "protect-ALL-destroy"), None)
            gh("PUT" if match else "POST", base + "/rulesets" + (f"/{match['id']}" if match else ""), ruleset())
    print("Controls configured. Upload the operations App PEM only to the aws-destroy environment secret.")
