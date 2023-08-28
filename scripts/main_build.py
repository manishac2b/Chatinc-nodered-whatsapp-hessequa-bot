import base64
import json
import os
import subprocess
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, TypedDict

PROJECT = os.environ["PROJECT"]
IMAGE = os.environ["IMAGE"]
DOCKER_REPO = os.environ["DOCKER_REPO"]
ALERT_URL = os.environ["ALERT_URL"]
ALERT_API_KEY = os.environ["ALERT_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
CALLBACK_CODE = os.environ["CODEBUILD_RESOLVED_SOURCE_VERSION"]
CODEBUILD_SRC_DIR = os.environ["CODEBUILD_SRC_DIR"]
PACKAGE_JSON = Path(CODEBUILD_SRC_DIR) / Path("package.json")
ENVIRONMENT_MD = Path(CODEBUILD_SRC_DIR) / Path("ENVIRONMENT.md")
HARBOR_USERNAME = os.environ["HARBOR_USERNAME"]
HARBOR_PASSWORD = os.environ["HARBOR_PASSWORD"]


SUCCESS = 0
VERSION_ALREADY_EXIST = 1
DOCKER_BUILD_AND_PUSH_ERROR = 2
CRITICAL_ERROR = 1000


class DockerTags(TypedDict):
    name: str
    tags: List[str]


def send_alert(
    version_string: str,
    project: str,
    code: int = SUCCESS,
    reason: str = "Build crashed",
):
    success = code <= 0
    payload = {
        "callback_code": CALLBACK_CODE,
        "success": success,
        "version": version_string,
        "code": code,
        "project": project,
        "image": IMAGE,
    }
    if success and ENVIRONMENT_MD.exists() and ENVIRONMENT_MD.is_file():
        with ENVIRONMENT_MD.open("r", encoding="utf8") as f:
            payload["env_variables"] = f.read()
    if not success:
        payload["reason"] = reason
    request = urllib.request.Request(
        ALERT_URL,
        json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": ALERT_API_KEY},
    )
    urllib.request.urlopen(request).close()


def get_version():
    url = "https://{DOCKER_REPO}/v2/{project}/{image}/tags/list"
    with PACKAGE_JSON.open() as pjson:
        pack = json.load(pjson)
        version: str = pack["version"]
    auth_header = base64.b64encode(
        f"{HARBOR_USERNAME}:{HARBOR_PASSWORD}".encode()
    ).decode()
    request = urllib.request.Request(
        url.format(project=PROJECT, image=IMAGE, DOCKER_REPO=DOCKER_REPO),
        headers={
            "Authorization": f"Basic {auth_header}",
        },
    )
    try:
        with urllib.request.urlopen(request) as stream:
            result: DockerTags = json.load(stream)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, version
        else:
            raise Exception("Problems with request to docker registry")
    if version in set(result["tags"]):
        return True, version
    else:
        return False, version


def build_and_push(version: str):
    build_command = [
        "docker",
        "build",
        "--build-arg",
        f"GITHUB_TOKEN={GITHUB_TOKEN}",
        "-t",
        f"{DOCKER_REPO}/{PROJECT}/{IMAGE}:latest",
        "-t",
        f"{DOCKER_REPO}/{PROJECT}/{IMAGE}:{version}",
        ".",
    ]
    print(f"\n  + {' '.join(build_command)}\n", flush=True)
    build = subprocess.run(
        build_command,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if build.returncode != 0:
        return False, "Docker build crashed"
    push_command = [
        "docker",
        "push",
        "--all-tags",
        f"{DOCKER_REPO}/{PROJECT}/{IMAGE}",
    ]
    print(f"\n  + {' '.join(push_command)}\n", flush=True)
    push = subprocess.run(
        push_command,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if push.returncode != 0:
        return False, "Docker push crashed"
    return True, ""


if __name__ == "__main__":
    version = None
    try:
        exist, version = get_version()
        if exist:
            send_alert(version, PROJECT, VERSION_ALREADY_EXIST, "Version already exist")
            print(
                f"\n {PROJECT}/{IMAGE}:{version} already exist\n Skipping...\n",
                flush=True,
            )
        else:
            success, reason = build_and_push(version)
            if not success:
                send_alert(version, PROJECT, DOCKER_BUILD_AND_PUSH_ERROR, reason)
                sys.exit(DOCKER_BUILD_AND_PUSH_ERROR)
            else:
                send_alert(version, PROJECT)
    except Exception as e:
        send_alert(version or "", PROJECT, CRITICAL_ERROR, str(e))
        print(e)
        print(traceback.format_exc())
        sys.exit(CRITICAL_ERROR)
