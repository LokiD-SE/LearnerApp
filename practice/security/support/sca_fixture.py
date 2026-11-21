"""Synthetic supply chain data for the dependency lesson (prefix sca_). Nothing here is real or fetched.

One fictional application, ``sandpay-checkout`` 4.2.0, and the same inventory written in two SBOM formats
(CycloneDX 1.7 JSON and SPDX 2.3 JSON), a list of OSV-shaped advisories with made-up ids (``SPSA-2026-...``),
made-up exploitation data, and good and bad pinning files. Every package name starts with ``sandpay-``; the
hashes are real SHA-256 digests of made-up byte strings, so the pinning files are well formed.

The dependency graph (the cycle is on purpose - npm and Python graphs have them)::

    sandpay-checkout -> http, crypto, log, widgets
    http -> json, idna          log -> template, json          template -> log
    widgets -> widgets-core
"""

from __future__ import annotations

import base64
import hashlib

ROOT = ("sandpay-checkout", "4.2.0")

# name, version, ecosystem (purl type), supplier ("" = none recorded), has a purl
_PACKAGES = [
    ("sandpay-http", "2.3.1", "pypi", "SandPay Open Source", True),
    ("sandpay-crypto", "0.9.2", "pypi", "SandPay Open Source", True),
    ("sandpay-log", "3.1.0", "pypi", "SandPay Open Source", True),
    ("sandpay-widgets", "3.2.0", "npm", "SandPay Open Source", True),
    ("sandpay-widgets-core", "1.0.3", "npm", "SandPay Open Source", True),
    ("sandpay-json", "1.4.0", "pypi", "SandPay Open Source", True),
    ("sandpay-idna", "2.9.0", "pypi", "", True),
    ("sandpay-template", "5.0.1", "pypi", "SandPay Open Source", False),
]

GRAPH = {
    "sandpay-checkout": ["sandpay-http", "sandpay-crypto", "sandpay-log", "sandpay-widgets"],
    "sandpay-http": ["sandpay-json", "sandpay-idna"],
    "sandpay-crypto": [],
    "sandpay-log": ["sandpay-template", "sandpay-json"],
    "sandpay-template": ["sandpay-log"],
    "sandpay-json": [],
    "sandpay-idna": [],
    "sandpay-widgets": ["sandpay-widgets-core"],
    "sandpay-widgets-core": [],
}

_BY_NAME = {p[0]: p for p in _PACKAGES}


def purl(name: str) -> str:
    _, version, eco, _, has = _BY_NAME[name]
    return f"pkg:{eco}/{name}@{version}" if has else ""


def _ref(name: str) -> str:
    """The CycloneDX bom-ref: the purl when there is one, otherwise name@version."""
    if name == ROOT[0]:
        return f"{ROOT[0]}@{ROOT[1]}"
    return purl(name) or f"{name}@{_BY_NAME[name][1]}"


def _cdx_component(name: str) -> dict:
    _, version, _, supplier, _ = _BY_NAME[name]
    comp: dict = {"type": "library", "bom-ref": _ref(name), "name": name, "version": version}
    if supplier:
        comp["supplier"] = {"name": supplier}
    if purl(name):
        comp["purl"] = purl(name)
    return comp


def _cyclonedx() -> dict:
    widgets = _cdx_component("sandpay-widgets")
    widgets["components"] = [_cdx_component("sandpay-widgets-core")]  # nested, as CycloneDX allows
    flat = [_cdx_component(n) for n in
            ("sandpay-http", "sandpay-crypto", "sandpay-log", "sandpay-json", "sandpay-idna", "sandpay-template")]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": "urn:uuid:3e671687-395b-41f5-a30f-a58921a69b79",
        "version": 1,
        "metadata": {
            "timestamp": "2026-11-21T10:00:00Z",
            "component": {"type": "application", "bom-ref": _ref(ROOT[0]), "name": ROOT[0], "version": ROOT[1]},
        },
        "components": [*flat[:3], widgets, *flat[3:]],
        "dependencies": [
            {"ref": _ref(src), "dependsOn": [_ref(dst) for dst in dsts]} for src, dsts in GRAPH.items()
        ],
    }


def _spdx_id(name: str) -> str:
    return "SPDXRef-Package-" + name


def _spdx_package(name: str) -> dict:
    _, version, _, supplier, _ = _BY_NAME[name]
    pkg: dict = {
        "SPDXID": _spdx_id(name),
        "name": name,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "supplier": f"Organization: {supplier}" if supplier else "NOASSERTION",
    }
    if purl(name):
        pkg["externalRefs"] = [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceType": "purl",
            "referenceLocator": purl(name),
        }]
    return pkg


def _spdx() -> dict:
    root = {"SPDXID": _spdx_id(ROOT[0]), "name": ROOT[0], "versionInfo": ROOT[1],
            "downloadLocation": "NOASSERTION", "supplier": "Organization: SandPay Open Source"}
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
                      "relatedSpdxElement": root["SPDXID"]}]
    for src, dsts in GRAPH.items():
        for dst in dsts:
            relationships.append({"spdxElementId": _spdx_id(src), "relationshipType": "DEPENDS_ON",
                                  "relatedSpdxElement": _spdx_id(dst)})
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "sandpay-checkout-4.2.0",
        "documentNamespace": "https://sbom.sandpay.example/spdx/sandpay-checkout-4.2.0",
        "creationInfo": {"created": "2026-11-21T10:00:00Z", "creators": ["Tool: practice-sbom-generator"]},
        "packages": [root, *[_spdx_package(p[0]) for p in _PACKAGES]],
        "relationships": relationships,
    }


CYCLONEDX_BOM = _cyclonedx()
SPDX_DOC = _spdx()


def _advisory(adv_id: str, ecosystem: str, name: str, events: list[dict], score: float, summary: str) -> dict:
    return {
        "id": adv_id,
        "summary": summary,
        "affected": [{"package": {"ecosystem": ecosystem, "name": name},
                      "ranges": [{"type": "SEMVER", "events": events}]}],
        "database_specific": {"cvss_v4_score": score},
    }


# OSV-shaped (https://ossf.github.io/osv-schema/): one type per event object. Scores, ids and flaws are made up.
ADVISORIES = [
    _advisory("SPSA-2026-0001", "PyPI", "sandpay-json", [{"introduced": "0"}, {"fixed": "1.4.2"}], 9.1,
              "Unbounded recursion on deeply nested documents (synthetic)"),
    _advisory("SPSA-2026-0002", "PyPI", "sandpay-http", [{"introduced": "2.0.0"}, {"fixed": "2.3.0"}], 7.5,
              "Header folding accepted (synthetic) - fixed before the version we ship"),
    _advisory("SPSA-2026-0003", "PyPI", "sandpay-crypto", [{"introduced": "0"}, {"last_affected": "0.9.2"}], 5.9,
              "Weak default nonce source (synthetic) - no fixed version exists"),
    _advisory("SPSA-2026-0004", "npm", "sandpay-widgets-core", [{"introduced": "1.0.0"}, {"fixed": "1.0.10"}], 6.1,
              "Markup passed through an unescaped template (synthetic)"),
    _advisory("SPSA-2026-0005", "PyPI", "sandpay-log", [{"introduced": "3.0.0"}, {"fixed": "3.1.0"}], 8.8,
              "Log injection through newlines (synthetic) - we ship exactly the fixed version"),
    _advisory("SPSA-2026-0006", "npm", "sandpay-json", [{"introduced": "0"}, {"fixed": "9.9.9"}], 9.8,
              "Same package name as our PyPI dependency, but a different ecosystem (synthetic)"),
    _advisory("SPSA-2026-0007", "PyPI", "sandpay-idna", [{"introduced": "2.0.0"}, {"fixed": "2.10.0"}], 3.7,
              "Label length check skipped (synthetic) - 2.9.0 is older than 2.10.0"),
]

# Pretend exploitation data. KNOWN_EXPLOITED stands in for a KEV-style list; EPSS is a 0-1 probability.
KNOWN_EXPLOITED = {"SPSA-2026-0003"}
EPSS = {
    "SPSA-2026-0001": 0.04,
    "SPSA-2026-0003": 0.01,
    "SPSA-2026-0004": 0.02,
    "SPSA-2026-0007": 0.003,
}


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sri(label: str) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(label.encode()).digest()).decode()


GOOD_REQUIREMENTS = f"""\
# every requirement pinned with == and hashed (pip hash-checking mode)
--index-url https://pypi.sandpay.example/simple
sandpay-http==2.3.1 \\
    --hash=sha256:{_sha("sandpay-http-2.3.1-wheel")} \\
    --hash=sha256:{_sha("sandpay-http-2.3.1-sdist")}
sandpay-json==1.4.2 --hash=sha256:{_sha("sandpay-json-1.4.2-wheel")}  # fixed for SPSA-2026-0001
"""

BAD_REQUIREMENTS = f"""\
sandpay-http==2.3.1 --hash=sha256:{_sha("sandpay-http-2.3.1-wheel")}
sandpay-log>=3.0
sandpay-crypto==0.9.*  --hash=sha256:{_sha("sandpay-crypto-0.9.2-wheel")}
sandpay-idna
sandpay-template==5.0.1 \\
    --hash=md5:{hashlib.md5(b"sandpay-template").hexdigest()}
"""

_REGISTRY = "https://registry.npmjs.org"

GOOD_LOCK = {
    "name": "sandpay-checkout-web",
    "version": "4.2.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {"name": "sandpay-checkout-web", "version": "4.2.0", "dependencies": {"sandpay-widgets": "^3.2.0"}},
        "node_modules/sandpay-widgets": {
            "version": "3.2.0",
            "resolved": f"{_REGISTRY}/sandpay-widgets/-/sandpay-widgets-3.2.0.tgz",
            "integrity": _sri("sandpay-widgets-3.2.0"),
        },
        "node_modules/sandpay-widgets-core": {
            "version": "1.0.3",
            "resolved": f"{_REGISTRY}/sandpay-widgets-core/-/sandpay-widgets-core-1.0.3.tgz",
            "integrity": _sri("sandpay-widgets-core-1.0.3"),
        },
        "node_modules/sandpay-local-tool": {"resolved": "tools/local", "link": True},
    },
}

BAD_LOCK = {
    "name": "sandpay-checkout-web",
    "version": "4.2.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {"name": "sandpay-checkout-web", "version": "4.2.0"},
        "node_modules/a-plain-http": {
            "version": "1.0.0",
            "resolved": "http://registry.npmjs.org/a-plain-http/-/a-plain-http-1.0.0.tgz",
            "integrity": _sri("a-plain-http-1.0.0"),
        },
        "node_modules/b-other-host": {
            "version": "2.0.0",
            "resolved": "https://mirror.sandpay.example/b-other-host/-/b-other-host-2.0.0.tgz",
            "integrity": _sri("b-other-host-2.0.0"),
        },
        "node_modules/c-no-integrity": {
            "version": "3.0.0",
            "resolved": f"{_REGISTRY}/c-no-integrity/-/c-no-integrity-3.0.0.tgz",
        },
        "node_modules/d-sha1": {
            "version": "4.0.0",
            "resolved": f"{_REGISTRY}/d-sha1/-/d-sha1-4.0.0.tgz",
            "integrity": "sha1-" + base64.b64encode(hashlib.sha1(b"d-sha1-4.0.0").digest()).decode(),
        },
        "node_modules/e-git-branch": {
            "version": "5.0.0",
            "resolved": "git+https://git.sandpay.example/e-git-branch.git#main",
        },
        "node_modules/f-git-pinned": {
            "version": "6.0.0",
            "resolved": "git+https://git.sandpay.example/f-git-pinned.git#" + "0123456789abcdef0123456789abcdef01234567",
        },
        "node_modules/g-no-resolved": {"version": "7.0.0", "integrity": _sri("g-no-resolved-7.0.0")},
    },
}
