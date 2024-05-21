# -*- coding: utf-8 -*-

import email.message
import os
import select
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest
import yaml

from muttdown import main
from muttdown.config import Config
from muttdown.main import convert_tree, process_message


@pytest.fixture
def basic_config():
    return Config()


@pytest.fixture
def tempdir():
    # workaround because pytest's bultin tmpdir fixture is broken on python 3.3
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    finally:
        shutil.rmtree(dirname)


@pytest.fixture
def config_with_css(tempdir):
    with open("%s/test.css" % tempdir, "w") as f:
        f.write("html, body, p { font-family: serif; }\n")
    c = Config()
    c.merge_config({"css_file": "%s/test.css" % tempdir})
    return c


def test_unmodified_no_match(basic_config):
    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.set_payload("This message has no sigil")

    converted = process_message(msg, basic_config)
    assert converted == msg


def test_simple_message(basic_config):
    msg = MIMEMultipart()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.preamble = "Outer preamble"

    msg.attach(MIMEText("!m This is the main message body"))

    attachment = MIMEText("this is an attachment", "x-misc")
    attachment.add_header("Content-Disposition", "attachment")
    msg.attach(attachment)

    converted, _ = convert_tree(msg, basic_config)
    assert converted["Subject"] == "Test Message"
    assert converted["From"] == "from@example.com"
    assert converted["To"] == "to@example.com"
    assert converted.get("Bcc", None) is None
    assert isinstance(converted, MIMEMultipart)
    assert converted.preamble == "Outer preamble"
    assert len(converted.get_payload()) == 2
    alternatives_part = converted.get_payload()[0]
    assert isinstance(alternatives_part, MIMEMultipart)
    assert alternatives_part.get_content_type() == "multipart/alternative"
    assert len(alternatives_part.get_payload()) == 2
    text_part = alternatives_part.get_payload()[0]
    html_part = alternatives_part.get_payload()[1]
    assert isinstance(text_part, MIMEText)
    assert text_part.get_content_type() == "text/plain"
    assert isinstance(html_part, MIMEText)
    assert html_part.get_content_type() == "text/html"
    attachment_part = converted.get_payload()[1]
    assert isinstance(attachment_part, MIMEText)
    assert attachment_part["Content-Disposition"] == "attachment"
    assert attachment_part.get_content_type() == "text/x-misc"


def test_with_css(config_with_css):
    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.set_payload("!m\n\nThis is a message")

    converted, _ = convert_tree(msg, config_with_css)
    assert isinstance(converted, MIMEMultipart)
    assert len(converted.get_payload()) == 2
    text_part = converted.get_payload()[0]
    assert text_part.get_payload(decode=True) == b"!m\n\nThis is a message"
    html_part = converted.get_payload()[1]
    assert (
        html_part.get_payload(decode=True)
        == b'<p style="font-family: serif">This is a message</p>'
    )


def test_fenced(basic_config):
    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.preamble = "Outer preamble"

    msg.set_payload("!m This is the main message body\n\n```\nsome code\n```\n")

    converted, _ = convert_tree(msg, basic_config)
    assert isinstance(converted, MIMEMultipart)
    assert len(converted.get_payload()) == 2
    html_part = converted.get_payload()[1]
    assert (
        html_part.get_payload(decode=True)
        == b"<p>This is the main message body</p>\n<pre><code>some code\n</code></pre>"
    )


def test_headers_when_multipart_signed(basic_config):
    msg = MIMEMultipart("signed")
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.preamble = "Outer preamble"

    msg.attach(MIMEText("!m This is the main message body"))
    msg.attach(MIMEApplication("signature here", "pgp-signature", name="signature.asc"))

    converted, _ = convert_tree(msg, basic_config)

    assert converted["Subject"] == "Test Message"
    assert converted["From"] == "from@example.com"
    assert converted["To"] == "to@example.com"

    assert isinstance(converted, MIMEMultipart)
    assert converted.preamble == "Outer preamble"
    assert len(converted.get_payload()) == 2
    assert converted.get_content_type() == "multipart/alternative"
    html_part = converted.get_payload()[0]
    original_signed_part = converted.get_payload()[1]
    assert isinstance(html_part, MIMEText)
    assert html_part.get_content_type() == "text/html"
    assert isinstance(original_signed_part, MIMEMultipart)
    assert original_signed_part.get_content_type() == "multipart/signed"
    assert original_signed_part["Subject"] is None
    text_part = original_signed_part.get_payload()[0]
    signature_part = original_signed_part.get_payload()[1]
    assert text_part.get_content_type() == "text/plain"
    assert signature_part.get_content_type() == "application/pgp-signature"


class MockSmtpServer(object):
    def __init__(self):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.bind(("127.0.0.1", 0))
        self.address = self._s.getsockname()[0:2]
        self._t = None
        self._started = threading.Event()
        self.messages = []
        self.running = False

    def start(self):
        self._t = threading.Thread(target=self.run)
        self._t.start()
        if self._started.wait(5) is not True:
            raise ValueError("SMTP Server Thread failed to start!")

    def run(self):
        if hasattr(ssl, "create_default_context"):
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.load_cert_chain(
            certfile="tests/data/cert.pem", keyfile="tests/data/key.pem"
        )
        self._s.listen(128)
        self._started.set()
        self.running = True
        while self.running:
            r, _, x = select.select([self._s], [self._s], [self._s], 0.5)
            if r:
                start = time.time()
                conn, addr = self._s.accept()
                conn = context.wrap_socket(conn, server_side=True)
                message = b""
                conn.sendall(b"220 localhost SMTP Fake\r\n")
                message += conn.recv(1024)
                conn.sendall(b"250-localhost\r\n250 DSN\r\n")
                # MAIL FROM
                message += conn.recv(1024)
                conn.sendall(b"250 2.1.0 Ok\r\n")
                # RCPT TO
                message += conn.recv(1024)
                conn.sendall(b"250 2.1.0 Ok\r\n")
                # DATA
                message += conn.recv(6)
                conn.sendall(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                while time.time() < start + 5:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    message += chunk
                    if b"\r\n.\r\n" in message:
                        break
                conn.sendall(b"250 2.1.0 Ok\r\n")
                message += conn.recv(1024)
                conn.sendall(b"221 Bye\r\n")
                conn.close()
                self.messages.append((addr, message))

    def stop(self):
        if self._t is not None:
            self.running = False
            self._t.join()


@pytest.fixture
def smtp_server():
    s = MockSmtpServer()
    s.start()
    try:
        yield s
    finally:
        s.stop()


def test_main_smtplib(tempdir, smtp_server, mocker):
    config_path = os.path.join(tempdir, "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(
            {
                "smtp_host": smtp_server.address[0],
                "smtp_port": smtp_server.address[1],
                "smtp_ssl": True,
            },
            f,
        )
    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.set_payload("This message has no sigil")
    mocker.patch.object(main, "read_message", return_value=msg.as_string())
    main.main(["-c", config_path, "-f", "from@example.com", "to@example.com"])

    assert len(smtp_server.messages) == 1
    attr, transcript = smtp_server.messages[0]
    assert b"Subject: Test Message" in transcript
    assert b"no sigil" in transcript


def test_main_passthru(tempdir, mocker):
    output_path = os.path.join(tempdir, "output")
    sendmail_path = os.path.join(tempdir, "sendmail")
    with open(sendmail_path, "w") as f:
        f.write("#!{0}\n".format(sys.executable))
        f.write("import sys\n")
        f.write('output_path = "{0}"\n'.format(output_path))
        f.write('open(output_path, "w").write(sys.stdin.read())\n')
        f.write("sys.exit(0)")
    os.chmod(sendmail_path, 0o750)
    config_path = os.path.join(tempdir, "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump({"sendmail": sendmail_path}, f)

    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.set_payload("This message has no sigil")
    mocker.patch.object(main, "read_message", return_value=msg.as_string())
    main.main(["-c", config_path, "-f", "from@example.com", "-s", "to@example.com"])

    with open(output_path, "rb") as f:
        transcript = f.read()
    assert b"Subject: Test Message" in transcript
    assert b"no sigil" in transcript


def test_raw_unicode(basic_config):
    raw_message = b"Date: Fri, 1 Mar 2019 17:54:06 -0800\nFrom: Test <test@example.com>\nTo: Test <test@example.com>\nSubject: Re: Fwd: Important: 2019 =?utf-8?Q?Securit?=\n =?utf-8?B?eSBVcGRhdGUg4oCU?=\nReferences: <BypjV000000000000000000000000000000000000000000000PNNK9E00HcUNxx_7QEaZBosNNgqKSw@sfdc.net>\n <CAPe=KFgfaFd5U7KX=3ugNs5vPzHkRgAij9md8TL-WX-ypEszug@mail.gmail.com>\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\nContent-Disposition: inline\nContent-Transfer-Encoding: 8bit\nUser-Agent: Mutt/1.11.3 (2019-02-01)\n\nThis is a test\n\n\nOn Fri, Mar 01, 2019 at 03:08:35PM -0800, Test Wrote:\n> :)\n> \n> \n> \xc3\x98  Text\n> \n> \xc2\xb7       text\n-- \nend\n"  # noqa
    mail = email.message_from_string(raw_message.decode("utf-8"))
    converted = process_message(mail, basic_config)
    assert converted["From"] == "Test <test@example.com>"
    assert "Ø" in converted.get_payload()


def test_assume_markdown(basic_config):
    msg = Message()
    msg["Subject"] = "Test Message"
    msg["From"] = "from@example.com"
    msg["To"] = "to@example.com"
    msg["Bcc"] = "bananas"
    msg.set_payload("This message has no **sigil**")

    basic_config.merge_config({"assume_markdown": True})

    converted = process_message(msg, basic_config)
    html_part = converted.get_payload()[1].get_payload(decode=True)
    assert html_part == b"<p>This message has no <strong>sigil</strong></p>"
