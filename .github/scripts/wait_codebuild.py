"""Wait for CodeBuild; propagate a failed deploy to the GitHub workflow."""
import json
import subprocess
import sys
import time

build_id = sys.argv[1]
deadline = time.monotonic() + 25 * 60
previous = None
while time.monotonic() < deadline:
    response = subprocess.run(["aws", "codebuild", "batch-get-builds", "--ids", build_id,
        "--output", "json"], capture_output=True, text=True, check=True)
    builds = json.loads(response.stdout)["builds"]
    if not builds:
        raise RuntimeError("CodeBuild did not return the requested build")
    build = builds[0]
    phase = (build.get("currentPhase"), build["buildStatus"])
    if phase != previous:
        print(f"CodeBuild {build_id}: {phase[0]} / {phase[1]}", flush=True)
        previous = phase
    if build["buildStatus"] != "IN_PROGRESS":
        link = build.get("logs", {}).get("deepLink", "")
        if link:
            print(f"Build logs: {link}", flush=True)
        sys.exit(0 if build["buildStatus"] == "SUCCEEDED" else 1)
    time.sleep(15)
raise TimeoutError("CodeBuild exceeded the workflow wait limit")

