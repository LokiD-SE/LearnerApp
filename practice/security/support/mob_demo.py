"""Prints every output the lesson mobile-app-security-testing shows. Run from practice/security:

    .venv/bin/python support/mob_demo.py            (uses the reference solutions)

It reads only the synthetic manifests, configs and dumps in support/mob_fixture.py. No device, no APK, no network.
"""

from __future__ import annotations

import platform
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "solutions"), str(ROOT / "support")]

import pyexpat  # noqa: E402
import mob_fixture as fx  # noqa: E402
from specialised import mob_manifest, mob_netconfig, mob_storage  # noqa: E402


def heading(text: str) -> None:
    print(f"\n=== {text}")


def show(findings, indent="  "):
    for item in findings:
        print(indent + " | ".join(item))


heading("runtime")
print(f"Python {platform.python_version()}, Expat {pyexpat.EXPAT_VERSION}")

heading("manifest audit: BAD_MANIFEST")
show(mob_manifest.audit_manifest(fx.BAD_MANIFEST))
heading("manifest audit: GOOD_MANIFEST")
print("  findings:", mob_manifest.audit_manifest(fx.GOOD_MANIFEST))
heading("manifest audit: no allowBackup written / dataExtractionRules written")
print("  ", mob_manifest.audit_manifest(fx.NO_ATTRS_MANIFEST))
print("  ", mob_manifest.audit_manifest(fx.RULES_MANIFEST))

heading("each manifest finding mapped to a MASWE weakness and a MASVS control (the lesson's own mapping)")
for code, where in mob_manifest.audit_manifest(fx.BAD_MANIFEST):
    maswe, title, control = fx.WEAKNESS_OF[code]
    print(f"  {code:<20} {where:<18} {maswe} {control}")

heading("target SDK of the two manifests")
print("  BAD:", mob_manifest.target_sdk(fx.BAD_MANIFEST), " GOOD:", mob_manifest.target_sdk(fx.GOOD_MANIFEST))

heading("why parse_manifest refuses a DOCTYPE: the standard parser expands an internal entity")
expanded = ET.fromstring(fx.ENTITY_MANIFEST).get("package")
print(f"  ET.fromstring(...) package attribute length: {len(expanded)}")
try:
    mob_manifest.parse_manifest(fx.ENTITY_MANIFEST)
except ValueError as error:
    print("  parse_manifest:", error)

heading("network security config audit: BAD_NSC")
show(mob_netconfig.audit_config(fx.BAD_NSC))
heading("network security config audit: GOOD_NSC")
print("  findings:", mob_netconfig.audit_config(fx.GOOD_NSC))

heading("effective cleartext, BAD_NSC")
for sdk in (27, 35):
    for host in ("legacy.sandpay.example", "api.sandpay.example", "other.example"):
        print(f"  target {sdk}  {host:<24} {mob_netconfig.effective_cleartext(fx.BAD_NSC, sdk, host)}")
heading("effective cleartext, NESTED_NSC (target 35)")
for host in ("www.sandpay.example", "secure.sandpay.example", "x.secure.sandpay.example", "notsandpay.example"):
    print(f"  {host:<28} {mob_netconfig.effective_cleartext(fx.NESTED_NSC, 35, host)}")
heading("effective cleartext, no configuration at all")
for sdk in (23, 27, 28, 35):
    print(f"  target {sdk}  {mob_netconfig.effective_cleartext(fx.EMPTY_NSC, sdk, 'api.sandpay.example')}")

heading("storage scan of the synthetic dump")
for path, kind, where in mob_storage.scan_dump(fx.DUMP):
    print(f"  {where:<8} {kind:<12} {path}")
heading("storage scan of the clean dump, and mask()")
print("  findings:", mob_storage.scan_dump(fx.CLEAN_DUMP))
print("  mask:", mob_storage.mask("demo-access-token-FAKE-0001"))
