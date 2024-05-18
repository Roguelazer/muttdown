import tempfile

from muttdown.config import Config


def test_smtp_password_literal():
    c = Config()
    c.merge_config({"smtp_password": "foo"})
    assert c.smtp_password == "foo"


def test_smtp_password_command():
    c = Config()
    c.merge_config({"smtp_password_command": 'sh -c "echo foo"'})
    assert c.smtp_password == "foo"


def test_css():
    c = Config()
    c.merge_config({"css_file": None})
    assert c.css == ""

    with tempfile.NamedTemporaryFile(delete=True) as css_file:
        css_file.write(b"html { background-color: black; }\n")
        css_file.flush()
        c.merge_config({"css_file": css_file.name})
        assert c.css == "html { background-color: black; }\n"


def test_assume_markdown():
    c = Config()
    assert not c.assume_markdown
    c.merge_config({"assume_markdown": True})
    assert c.assume_markdown
