"""Shared data for the mobile-app-security lesson (prefix ``mob_``). Everything here is synthetic.

SandPay Merchant is a fictional Android app. The manifests, network security configs and app-data dumps below
are written by hand in the shapes the Android documentation describes; no real APK was unpacked, and no token,
password or key in this file was ever issued. Nothing here touches a device or the network.

``CONTROLS`` holds the MASVS control statements as printed on mas.owasp.org on 21 November 2026.
``WEAKNESS_OF`` maps each finding code the exercises report to the MASWE weakness (and its MASVS control) whose
title and overview describe it - the mapping is the lesson's own reading, and the lesson says so.
"""

from __future__ import annotations

# --- MASVS control statements (MASVS 2.x group pages) -------------------------------------------------------
CONTROLS = {
    "MASVS-STORAGE-1": "The app securely stores sensitive data.",
    "MASVS-STORAGE-2": "The app prevents leakage of sensitive data.",
    "MASVS-NETWORK-1": "The app secures all network traffic according to the current best practices.",
    "MASVS-NETWORK-2": "The app performs identity pinning for all remote endpoints under the developer's control.",
    "MASVS-AUTH-1": "The app uses secure authentication and authorization protocols and follows the relevant best practices.",
    "MASVS-PLATFORM-1": "The app uses IPC mechanisms securely.",
    "MASVS-RESILIENCE-4": "The app implements anti-dynamic analysis techniques.",
}

# code -> (MASWE id, MASWE title, MASVS control). Titles as listed on the MASWE index, 21 November 2026.
WEAKNESS_OF = {
    "debuggable": ("MASWE-0063", "Debug Mechanisms Not Disabled", "MASVS-RESILIENCE-4"),
    "backup-allowed": ("MASWE-0006", "Sensitive Data Not Excluded From Backup", "MASVS-STORAGE-2"),
    "cleartext-manifest": ("MASWE-0026", "Network Traffic Not Encrypted", "MASVS-NETWORK-1"),
    "exported-open": ("MASWE-0018", "Lack of Authentication or Authorization on App Components", "MASVS-AUTH-1"),
    "exported-undeclared": ("MASWE-0018", "Lack of Authentication or Authorization on App Components", "MASVS-AUTH-1"),
    "cleartext-base": ("MASWE-0026", "Network Traffic Not Encrypted", "MASVS-NETWORK-1"),
    "cleartext-domain": ("MASWE-0026", "Network Traffic Not Encrypted", "MASVS-NETWORK-1"),
    "user-ca-trusted": ("MASWE-0027", "Insecure Certificate Validation", "MASVS-NETWORK-1"),
    "pin-expiry": ("MASWE-0028", "Insecure Identity Pinning", "MASVS-NETWORK-2"),
    "pin-no-backup": ("MASWE-0028", "Insecure Identity Pinning", "MASVS-NETWORK-2"),
    "token": ("MASWE-0001", "Sensitive Data Stored Unencrypted in Private Storage", "MASVS-STORAGE-1"),
    "password": ("MASWE-0001", "Sensitive Data Stored Unencrypted in Private Storage", "MASVS-STORAGE-1"),
    "private-key": ("MASWE-0001", "Sensitive Data Stored Unencrypted in Private Storage", "MASVS-STORAGE-1"),
}

# --- Android manifests --------------------------------------------------------------------------------------
BAD_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example.sandpay.merchant">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="27"/>
  <application
      android:label="SandPay Merchant"
      android:debuggable="true"
      android:allowBackup="true"
      android:usesCleartextTraffic="true">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
      </intent-filter>
    </activity>
    <activity android:name=".PayLinkActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <category android:name="android.intent.category.BROWSABLE"/>
        <data android:scheme="sandpay" android:host="pay"/>
      </intent-filter>
    </activity>
    <activity android:name=".ReceiptActivity">
      <intent-filter>
        <action android:name="example.sandpay.merchant.SHOW_RECEIPT"/>
        <category android:name="android.intent.category.DEFAULT"/>
      </intent-filter>
    </activity>
    <service android:name=".SyncService" android:exported="true"/>
    <provider android:name=".ReceiptProvider"
        android:authorities="example.sandpay.merchant.receipts"
        android:exported="true"/>
    <receiver android:name=".RefundReceiver" android:exported="true"
        android:permission="example.sandpay.merchant.permission.INTERNAL"/>
    <activity android:name=".SettingsActivity" android:exported="false"/>
    <service android:name=".UploadService"/>
  </application>
</manifest>
"""

GOOD_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example.sandpay.merchant">
  <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/>
  <application
      android:label="SandPay Merchant"
      android:allowBackup="false"
      android:usesCleartextTraffic="false"
      android:networkSecurityConfig="@xml/network_security_config">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
      </intent-filter>
    </activity>
    <activity android:name=".SettingsActivity" android:exported="false"/>
    <service android:name=".SyncService" android:exported="false"/>
    <provider android:name=".ReceiptProvider"
        android:authorities="example.sandpay.merchant.receipts"
        android:exported="false"/>
    <receiver android:name=".RefundReceiver" android:exported="true"
        android:permission="example.sandpay.merchant.permission.INTERNAL"/>
  </application>
</manifest>
"""

# allowBackup left out (the documented default is "true") but dataExtractionRules says what is backed up.
RULES_MANIFEST = """<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example.sandpay.merchant">
  <application android:dataExtractionRules="@xml/data_extraction_rules"/>
</manifest>
"""

NO_ATTRS_MANIFEST = """<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example.sandpay.merchant">
  <application/>
</manifest>
"""

# A DOCTYPE with an internal entity: the audit must refuse it, never expand it.
ENTITY_MANIFEST = """<?xml version="1.0"?>
<!DOCTYPE manifest [<!ENTITY a "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">]>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="&a;"><application/></manifest>
"""

# --- network security configs -------------------------------------------------------------------------------
BAD_NSC = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="true">
    <trust-anchors>
      <certificates src="system"/>
      <certificates src="user"/>
    </trust-anchors>
  </base-config>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="true">legacy.sandpay.example</domain>
  </domain-config>
  <domain-config>
    <domain includeSubdomains="true">api.sandpay.example</domain>
    <pin-set expiration="2026-01-01">
      <pin digest="SHA-256">AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</pin>
    </pin-set>
  </domain-config>
  <debug-overrides>
    <trust-anchors>
      <certificates src="user"/>
    </trust-anchors>
  </debug-overrides>
</network-security-config>
"""

GOOD_NSC = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false">
    <trust-anchors>
      <certificates src="system"/>
    </trust-anchors>
  </base-config>
  <domain-config>
    <domain includeSubdomains="true">api.sandpay.example</domain>
    <pin-set>
      <pin digest="SHA-256">AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</pin>
      <pin digest="SHA-256">BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=</pin>
    </pin-set>
  </domain-config>
  <debug-overrides>
    <trust-anchors>
      <certificates src="@raw/debug_cas"/>
    </trust-anchors>
  </debug-overrides>
</network-security-config>
"""

# The nested example from the Android documentation, with SandPay names: cleartext allowed under
# sandpay.example except for secure.sandpay.example (a nested domain-config inherits the parent's other values).
NESTED_NSC = """<network-security-config>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="true">sandpay.example</domain>
    <domain-config cleartextTrafficPermitted="false">
      <domain includeSubdomains="true">secure.sandpay.example</domain>
    </domain-config>
  </domain-config>
</network-security-config>
"""

# One domain-config for a single host only (includeSubdomains false) next to a broader rule.
EXACT_NSC = """<network-security-config>
  <base-config cleartextTrafficPermitted="false"/>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="false">status.sandpay.example</domain>
  </domain-config>
</network-security-config>
"""

EMPTY_NSC = "<network-security-config/>"

# --- an app-data dump (path -> text), as pulled from a rooted test device that you own ------------------------
PKG = "/data/data/example.sandpay.merchant"
DUMP = {
    f"{PKG}/shared_prefs/session.xml": (
        '<?xml version="1.0"?><map>'
        '<string name="theme">dark</string>'
        '<string name="access_token">demo-access-token-FAKE-0001</string>'
        '<string name="refresh_token">[REDACTED]</string>'
        "</map>"
    ),
    f"{PKG}/files/cache.json": '{"merchant": "m-demo", "password": "demo-pass-FAKE", "currency": "EUR"}',
    f"{PKG}/files/keystore.pem": "-----BEGIN PRIVATE KEY-----\nZGVtby1ub3QtYS1rZXk=\n-----END PRIVATE KEY-----\n",
    f"{PKG}/files/settings.txt": "language=en\nrefresh_interval=30\n",
    "/sdcard/Download/export.csv": "date,amount\n2026-11-20,12.50\napi_key=demo-export-key-FAKE\n",
    "/data/local/tmp/logcat.txt": (
        "11-20 10:00:01.123 D/Pay: starting checkout\n"
        "11-20 10:00:01.456 D/Http: Authorization: Bearer demo.bearer.FAKE.value\n"
        "11-20 10:00:02.001 I/Pay: done\n"
    ),
}

CLEAN_DUMP = {
    f"{PKG}/files/settings.txt": "language=en\n",
    f"{PKG}/shared_prefs/session.xml": '<map><string name="access_token">[REDACTED]</string></map>',
}
