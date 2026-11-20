"""Bounded publishing probes and registry operations used by the release workflow."""

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile


CENTRAL = "https://central.sonatype.com/api/v1/publisher"
MAVEN = "https://repo.maven.apache.org/maven2"
GHCR = "https://ghcr.io"
ZIP_LIMIT = 50 * 1024 * 1024


def request(url, method="GET", headers=None, data=None):
    try:
        with urlopen(Request(url, headers=headers or {}, data=data, method=method), timeout=25) as response:
            return response.status, response.headers, response.read(2 * 1024 * 1024)
    except HTTPError as response:
        return response.status, response.headers, response.read(16384)


class UnknownRegistryState(RuntimeError):
    pass


def require(response, codes, operation):
    status, _, data = response
    if status not in codes:
        if status == 429 or status >= 500:
            raise UnknownRegistryState(f"{operation}: unknown (HTTP {status})")
        raise RuntimeError(f"{operation}: HTTP {status}")
    return data


def encode(user, password):
    return base64.b64encode(f"{user}:{password}".encode()).decode()


def public_status(url):
    status, _, _ = request(url, "HEAD")
    if status == 404:
        return False
    require((status, {}, b""), {200}, f"Anonymous request to {url}")
    return True


def wait_for(probe, description, seconds=900):
    started = time.monotonic()
    delay = 5
    while True:
        try:
            if probe():
                print(f"{description} verified after {time.monotonic() - started:.0f}s")
                return
        except (UnknownRegistryState, URLError, TimeoutError) as error:
            print(f"::warning::{description}: {error}. Retrying observation.")
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise RuntimeError(f"{description} remains unverified after {seconds}s")
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 60)


def central_auth():
    missing = [name for name in ("CENTRAL_USERNAME", "CENTRAL_PASSWORD") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Configure Central Portal secrets: {', '.join(missing)}")
    return {"Authorization": "Bearer " + encode(os.environ["CENTRAL_USERNAME"], os.environ["CENTRAL_PASSWORD"])}


def central_pom(group, artifact, version):
    return f"{MAVEN}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"


def upload_to_central(bundle, name):
    import uuid

    if bundle.stat().st_size > ZIP_LIMIT:
        raise RuntimeError(f"{bundle} exceeds the template's {ZIP_LIMIT // 1024**2} MiB bundle budget")
    # The response identifies the deployment. A non-idempotent upload is never retried.
    boundary = uuid.uuid4().hex
    header = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"bundle\"; "
        'filename="bundle.zip"\r\nContent-Type: application/zip\r\n\r\n'
    ).encode()
    payload = header + bundle.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    query = urlencode({"name": name, "publishingType": "USER_MANAGED"})
    headers = dict(central_auth(), **{"Content-Type": f"multipart/form-data; boundary={boundary}"})
    data = require(request(f"{CENTRAL}/upload?{query}", "POST", headers, payload), {201}, "Central Portal upload")
    return str(uuid.UUID(data.decode().strip()))


def central_state(deployment_id, *, allow_failure=False):
    data = require(
        request(f"{CENTRAL}/status?{urlencode({'id': deployment_id})}", "POST", central_auth()),
        {200}, "Central deployment status",
    )
    response = json.loads(data)
    state = response["deploymentState"]
    if state == "FAILED" and not allow_failure:
        raise RuntimeError(f"Central Portal rejected deployment {deployment_id}. Inspect validation in the Portal.")
    return state


def activate_deployment(deployment_id):
    state = central_state(deployment_id)
    if state == "VALIDATED":
        require(
            request(f"{CENTRAL}/deployment/{deployment_id}", "POST", central_auth()),
            {204}, "Central Portal publish",
        )
    elif state not in {"PUBLISHING", "PUBLISHED"}:
        return False
    return True


def preflight_central():
    errors = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "probe.zip"
            with ZipFile(bundle, "w") as archive:
                archive.writestr("preflight/placeholder.txt", "Unpublished credential probe")
            deployment = upload_to_central(bundle, "kotlin-pipeline-credential-probe")
            wait_for(
                lambda: central_state(deployment, allow_failure=True) in {"FAILED", "VALIDATED"},
                "Credential probe droppable state", seconds=90,
            )
            require(
                request(f"{CENTRAL}/deployment/{deployment}", "DELETE", central_auth()),
                {204}, f"Delete staging probe {deployment}",
            )
        print("Central Portal accepted and removed a staging upload.")
    except (RuntimeError, OSError, ValueError) as error:
        errors.append(str(error))
    try:
        check_signing()
        print("PGP key can sign with the configured passphrase.")
    except (RuntimeError, OSError) as error:
        errors.append(str(error))
    if errors:
        raise RuntimeError("\n".join(errors))


def check_signing():
    if not os.environ.get("SIGNING_KEY"):
        raise RuntimeError("Configure the SIGNING_KEY secret and, if needed, SIGNING_PASSWORD.")
    with tempfile.TemporaryDirectory() as home:
        config = ["gpg", "--homedir", home, "--batch"]
        imported = subprocess.run(
            [*config, "--import"], input=os.environ["SIGNING_KEY"].encode(), capture_output=True,
        )
        probe = Path(home) / "probe"
        probe.write_text("Kotlin pipeline signing preflight\n", encoding="utf-8")
        signed = imported.returncode or subprocess.run(
            [*config, "--pinentry-mode", "loopback", "--passphrase-fd", "0", "--detach-sign", str(probe)],
            input=(os.environ.get("SIGNING_PASSWORD", "") + "\n").encode(), capture_output=True,
        ).returncode
        if signed:
            raise RuntimeError("Cannot sign with SIGNING_KEY and SIGNING_PASSWORD.")


@contextmanager
def ghcr_auth(repository, authenticated):
    repository = repository.lower()
    headers = {}
    actions = "pull"
    if authenticated:
        actions = "pull,push"
        headers["Authorization"] = "Basic " + encode(os.environ["GITHUB_ACTOR"], os.environ["GH_TOKEN"])
    token = require(
        request(f"{GHCR}/token?{urlencode({'service': 'ghcr.io', 'scope': f'repository:{repository}:{actions}'})}",
                headers=headers), {200}, "GHCR authorization",
    )
    yield {"Authorization": "Bearer " + json.loads(token)["token"]}


def preflight_ghcr(repository):
    repository = repository.lower()
    with ghcr_auth(repository, True) as headers:
        response = request(f"{GHCR}/v2/{repository}/blobs/uploads/", "POST", headers, b"")
        require(response, {202}, "GHCR write probe. Grant the repository Actions write access to the package")
        location = urljoin(GHCR, response[1]["Location"])
        if urlparse(location).netloc != "ghcr.io":
            raise RuntimeError("GHCR returned an unexpected upload host")
        require(request(location, "DELETE", headers), {204}, "Cancel GHCR upload probe")
    print("GHCR accepted and cancelled a blob upload.")


def ghcr_platforms(repository, tag, authenticated=False):
    repository = repository.lower()
    with ghcr_auth(repository, authenticated) as headers:
        headers["Accept"] = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"
        response = request(f"{GHCR}/v2/{repository}/manifests/{quote(tag, safe='')}", headers=headers)
    if response[0] == 404:
        return set()
    if response[0] in {401, 403} and not authenticated:
        raise RuntimeError("GHCR denies anonymous access. Make the package public in package settings.")
    return {
        f"{manifest['platform']['os']}/{manifest['platform']['architecture']}"
        for manifest in json.loads(require(response, {200}, "GHCR manifest visibility")).get("manifests", [])
    }
