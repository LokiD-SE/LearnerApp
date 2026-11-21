"""Checks exercises/specialised/mob_manifest.py: parsing without entities and the manifest audit."""

import pytest
import mob_fixture as fx
from specialised.mob_manifest import audit_manifest, parse_manifest, target_sdk

pytestmark = pytest.mark.exercise

WRAP = '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="x">{}</manifest>'


def app(attrs="", children=""):
    return WRAP.format(f"<application {attrs}>{children}</application>")


def test_the_bad_manifest_gives_exactly_the_expected_findings():
    assert audit_manifest(fx.BAD_MANIFEST) == [
        ("backup-allowed", "application"),
        ("cleartext-manifest", "application"),
        ("debuggable", "application"),
        ("exported-open", ".PayLinkActivity"),
        ("exported-open", ".ReceiptProvider"),
        ("exported-open", ".SyncService"),
        ("exported-undeclared", ".ReceiptActivity"),
    ]


def test_the_good_manifest_has_no_findings():
    assert audit_manifest(fx.GOOD_MANIFEST) == []


def test_every_finding_code_has_a_weakness_in_the_fixture_table():
    for code, _where in audit_manifest(fx.BAD_MANIFEST):
        maswe, title, control = fx.WEAKNESS_OF[code]
        assert maswe.startswith("MASWE-") and control in fx.CONTROLS


def test_a_missing_allow_backup_means_the_documented_default_which_is_true():
    assert audit_manifest(fx.NO_ATTRS_MANIFEST) == [("backup-allowed", "application")]


def test_data_extraction_rules_say_what_is_backed_up_so_it_is_not_flagged():
    assert audit_manifest(fx.RULES_MANIFEST) == []


def test_allow_backup_false_is_clean_and_true_is_flagged():
    assert audit_manifest(app('android:allowBackup="false"')) == []
    assert audit_manifest(app('android:allowBackup="true"')) == [("backup-allowed", "application")]


def test_debuggable_and_cleartext_are_read_from_the_application_element():
    flags = 'android:allowBackup="false" android:debuggable="true" android:usesCleartextTraffic="true"'
    assert audit_manifest(app(flags)) == [("cleartext-manifest", "application"), ("debuggable", "application")]
    flags = 'android:allowBackup="false" android:debuggable="false" android:usesCleartextTraffic="false"'
    assert audit_manifest(app(flags)) == []


def test_the_launcher_activity_may_be_exported_without_a_permission():
    launcher = (
        '<activity android:name=".Main" android:exported="true"><intent-filter>'
        '<action android:name="android.intent.action.MAIN"/>'
        '<category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity>'
    )
    assert audit_manifest(app('android:allowBackup="false"', launcher)) == []


def test_main_without_the_launcher_category_is_not_the_launcher():
    odd = (
        '<activity android:name=".Odd" android:exported="true"><intent-filter>'
        '<action android:name="android.intent.action.MAIN"/></intent-filter></activity>'
    )
    assert audit_manifest(app('android:allowBackup="false"', odd)) == [("exported-open", ".Odd")]


def test_a_permission_protects_an_exported_component():
    receiver = '<receiver android:name=".R" android:exported="true" android:permission="x.permission.P"/>'
    assert audit_manifest(app('android:allowBackup="false"', receiver)) == []


def test_a_provider_that_does_not_declare_exported_is_reported():
    provider = '<provider android:name=".P" android:authorities="x.p"/>'
    assert audit_manifest(app('android:allowBackup="false"', provider)) == [("exported-undeclared", ".P")]


def test_a_service_with_no_filter_and_no_exported_is_not_reported():
    service = '<service android:name=".S"/>'
    assert audit_manifest(app('android:allowBackup="false"', service)) == []


def test_exported_false_is_never_reported():
    items = (
        '<activity android:name=".A" android:exported="false"><intent-filter><action android:name="x"/></intent-filter></activity>'
        '<provider android:name=".P" android:authorities="x.p" android:exported="false"/>'
    )
    assert audit_manifest(app('android:allowBackup="false"', items)) == []


def test_an_activity_alias_is_checked_too():
    alias = '<activity-alias android:name=".Alias" android:targetActivity=".A" android:exported="true"/>'
    assert audit_manifest(app('android:allowBackup="false"', alias)) == [("exported-open", ".Alias")]


def test_no_application_element_gives_no_findings():
    assert audit_manifest(WRAP.format("")) == []


def test_the_result_is_sorted_and_has_no_repeats():
    result = audit_manifest(fx.BAD_MANIFEST)
    assert result == sorted(set(result))


def test_a_doctype_or_entity_is_refused_and_never_expanded():
    with pytest.raises(ValueError):
        parse_manifest(fx.ENTITY_MANIFEST)
    with pytest.raises(ValueError):
        audit_manifest(fx.ENTITY_MANIFEST)
    with pytest.raises(ValueError):
        parse_manifest('<!doctype manifest><manifest/>')


def test_text_that_is_not_xml_raises_value_error():
    with pytest.raises(ValueError):
        parse_manifest("<manifest><application></manifest>")


def test_target_sdk_is_an_integer_or_none():
    assert target_sdk(fx.BAD_MANIFEST) == 27
    assert target_sdk(fx.GOOD_MANIFEST) == 35
    assert target_sdk(fx.NO_ATTRS_MANIFEST) is None
