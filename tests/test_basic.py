from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pytest

from muttdown.main import convert_tree
from muttdown.config import Config


@pytest.fixture
def basic_config():
    return Config()


def test_simple_message(basic_config):
    msg = MIMEMultipart()
    msg['Subject'] = 'Test Message'
    msg['From'] = 'from@example.com'
    msg['To'] = 'to@example.com'
    msg['Bcc'] = 'bananas'
    msg.preamble = 'Outer preamble'

    msg.attach(MIMEText("!m This is the main message body"))

    attachment = MIMEText('this is an attachment', 'x-misc')
    attachment.add_header('Content-Disposition', 'attachment')
    msg.attach(attachment)

    converted, _ = convert_tree(msg, basic_config)
    assert converted['Subject'] == 'Test Message'
    assert converted['From'] == 'from@example.com'
    assert converted['To'] == 'to@example.com'
    assert converted.get('Bcc', None) is None
    assert isinstance(converted, MIMEMultipart)
    assert converted.preamble == 'Outer preamble'
    assert len(converted.get_payload()) == 2
    alternatives_part = converted.get_payload()[0]
    assert isinstance(alternatives_part, MIMEMultipart)
    assert alternatives_part.get_content_type() == 'multipart/alternative'
    assert len(alternatives_part.get_payload()) == 2
    text_part = alternatives_part.get_payload()[0]
    html_part = alternatives_part.get_payload()[1]
    assert isinstance(text_part, MIMEText)
    assert text_part.get_content_type() == 'text/plain'
    assert isinstance(html_part, MIMEText)
    assert html_part.get_content_type() == 'text/html'
    attachment_part = converted.get_payload()[1]
    assert isinstance(attachment_part, MIMEText)
    assert attachment_part['Content-Disposition'] == 'attachment'
    assert attachment_part.get_content_type() == 'text/x-misc'
