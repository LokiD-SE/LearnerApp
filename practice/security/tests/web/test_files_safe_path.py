import pytest
from files_fixture import make_tree
from web.files_safe_path import PathRejected, naive_read, read_public, resolve_inside

pytestmark = pytest.mark.exercise

TRAVERSALS = [
    "../secret.txt",
    "../../secret.txt",
    "reports/../../secret.txt",
    "..\\secret.txt",
    "..%2fsecret.txt",  # still encoded: the framework decoded once already, so this is a literal name
    "%2e%2e/secret.txt",
    "....//secret.txt",
    "/etc/passwd",
    "/secret.txt",
    "C:\\Windows\\win.ini",
    "C:win.ini",
    "\\\\server\\share\\x.txt",
    "../uploads-old/old.txt",  # a sibling that shares the prefix of the base
    "terms.txt\x00.png",
    "terms.txt:stream",
    "terms.txt::$DATA",
    "",
    ".",
    "..",
    ".hidden",
    "reports/",
    "a/b/c/d/e.txt",
    "name with spaces.txt",
]


@pytest.fixture
def tree(tmp_path):
    t = make_tree(tmp_path)
    return t


def test_the_original_is_really_vulnerable(tree):
    # '....//' becomes '../' after the one-pass removal, and the base is dropped for an absolute name.
    assert naive_read(tree["base"], "....//secret.txt") == "secret.txt\n"
    assert naive_read(tree["base"], str(tree["secret"])) == "secret.txt\n"


def test_normal_files_resolve_to_their_real_path(tree):
    assert resolve_inside(tree["base"], "terms.txt") == tree["base"].resolve() / "terms.txt"
    assert resolve_inside(tree["base"], "reports/2026-11.txt").read_text() == "uploads/reports/2026-11.txt\n"


@pytest.mark.parametrize("name", TRAVERSALS)
def test_every_escape_and_odd_name_is_rejected(tree, name):
    with pytest.raises(PathRejected):
        resolve_inside(tree["base"], name)


def test_a_sibling_folder_with_the_same_prefix_is_outside(tree):
    # A string-prefix check would accept this: ".../uploads-old/old.txt".startswith(".../uploads").
    with pytest.raises(PathRejected):
        resolve_inside(tree["base"], "../uploads-old/old.txt")
    assert str(tree["old"] / "old.txt").startswith(str(tree["base"]))


def test_a_link_that_stays_inside_is_fine(tree):
    assert resolve_inside(tree["base"], "link-inside.txt") == tree["base"].resolve() / "terms.txt"


def test_a_link_that_leaves_the_base_is_rejected(tree):
    with pytest.raises(PathRejected):
        resolve_inside(tree["base"], "link-outside.txt")


def test_missing_files_and_folders_are_not_found_not_rejected(tree):
    for name in ["nope.txt", "reports/nope.txt", "reports"]:
        with pytest.raises(FileNotFoundError):
            resolve_inside(tree["base"], name)


def test_a_base_given_with_dots_and_a_trailing_slash_still_works(tree):
    messy = str(tree["base"].parent / "uploads" / ".." / "uploads") + "/"
    assert resolve_inside(messy, "terms.txt").name == "terms.txt"
    with pytest.raises(PathRejected):
        resolve_inside(messy, "../secret.txt")


def test_read_public_serves_files_and_hides_everything_else_the_same_way(tree):
    assert read_public(tree["base"], "terms.txt") == (200, "uploads/terms.txt\n")
    answers = {read_public(tree["base"], n) for n in [*TRAVERSALS, "nope.txt", "reports", "link-outside.txt"]}
    assert answers == {(404, "file not found")}


def test_the_secret_text_never_leaves(tree):
    for name in TRAVERSALS + ["link-outside.txt"]:
        status, text = read_public(tree["base"], name)
        assert "secret.txt" not in text and status == 404
