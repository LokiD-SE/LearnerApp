import itertools

import pytest
from files_fixture import HTML, JPG, PDF, PNG
from web.files_upload_check import (
    ALLOWED,
    MAX_BYTES,
    StoredUpload,
    UploadRejected,
    download_headers,
    validate_upload,
)

pytestmark = pytest.mark.exercise


def ids():
    counter = itertools.count(1)
    return lambda: f"id{next(counter)}"


def accept(filename, data=PNG, declared="image/png"):
    return validate_upload(filename, declared, data, ids())


def test_the_three_allowed_types_are_accepted_and_renamed():
    assert accept("receipt.png", PNG) == StoredUpload("id1.png", "image/png", len(PNG))
    assert accept("photo.jpg", JPG) == StoredUpload("id1.jpg", "image/jpeg", len(JPG))
    assert accept("dispute.pdf", PDF) == StoredUpload("id1.pdf", "application/pdf", len(PDF))


def test_the_stored_name_never_contains_the_clients_name():
    stored = accept("shop-a-invoice.PNG", PNG).stored_name
    assert stored == "id1.png" and "invoice" not in stored


def test_the_default_name_is_random_and_hex():
    a = validate_upload("a.png", "image/png", PNG).stored_name
    b = validate_upload("a.png", "image/png", PNG).stored_name
    assert a != b and a.endswith(".png") and len(a) == 32 + 4


def test_extension_case_does_not_matter():
    assert accept("SCAN.PdF", PDF).stored_name == "id1.pdf"
    assert accept("x.JPG", JPG).content_type == "image/jpeg"


@pytest.mark.parametrize(
    "name",
    ["evil.php", "evil.phtml", "evil.php5", "evil.jsp", "evil.aspx", "evil.html", "evil.svg", "evil.exe",
     "evil.png.php", "evil.pdf.html", "evil", ".png", "png", "evil.png.", "evil.png ", "evil.png\x00.php",
     "evil.png:.php", "evil.php::$DATA", "../evil.png", "a/b.png", "a\\b.png", "x" * 120 + ".png"],
)
def test_bad_names_and_extensions_are_rejected(name):
    with pytest.raises(UploadRejected):
        accept(name, PNG)


def test_a_double_extension_is_judged_by_the_last_one_and_renamed():
    # "evil.php.png" is a PNG by its last extension and its bytes; the stored name has no trace of ".php".
    assert accept("evil.php.png", PNG).stored_name == "id1.png"


def test_the_signature_must_match_the_extension():
    for name, data in [("a.png", HTML), ("a.png", PDF), ("a.pdf", PNG), ("a.jpg", PNG), ("a.png", b"not an image")]:
        with pytest.raises(UploadRejected):
            accept(name, data)


def test_the_declared_content_type_is_ignored_both_ways():
    # Spoofed to look fine: HTML bytes declared as image/png are still rejected ...
    with pytest.raises(UploadRejected):
        accept("a.png", HTML, declared="image/png")
    # ... and a real PNG declared as text/html is accepted, with the type the SERVER decided.
    assert accept("a.png", PNG, declared="text/html").content_type == "image/png"
    assert accept("a.png", PNG, declared="").content_type == "image/png"


def test_size_limits():
    assert accept("a.png", PNG + b"x" * (MAX_BYTES - len(PNG))).size == MAX_BYTES
    with pytest.raises(UploadRejected):
        accept("a.png", PNG + b"x" * (MAX_BYTES - len(PNG) + 1))
    with pytest.raises(UploadRejected):
        accept("a.png", b"")


def test_the_allow_list_has_only_what_the_business_needs():
    assert set(ALLOWED) == {".png", ".jpg", ".pdf"}


def test_download_headers_make_the_file_a_download_not_a_page():
    headers = download_headers(StoredUpload("id1.png", "image/png", 10))
    assert headers == {
        "Content-Type": "image/png",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'attachment; filename="id1.png"',
    }


def test_a_rejection_says_which_rule_failed():
    with pytest.raises(UploadRejected, match="extension"):
        accept("evil.php", PNG)
    with pytest.raises(UploadRejected, match="content"):
        accept("a.png", HTML)
    with pytest.raises(UploadRejected, match="size"):
        accept("a.png", b"")
