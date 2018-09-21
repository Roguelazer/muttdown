from __future__ import print_function

import argparse
import sys
import smtplib
import re
import os.path
import email
import email.iterators
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import subprocess
import six

import markdown
import pynliner

from . import config
from . import __version__

__name__ = 'muttdown'


def convert_one(part, config):
    try:
        text = part.get_payload(decode=True)
        if not isinstance(text, six.text_type):
            # no, I don't know why decode=True sometimes fails to decode.
            text = text.decode('utf-8')
        if not text.startswith('!m'):
            return None
        text = re.sub('\s*!m\s*', '', text, re.M)
        if '\n-- \n' in text:
            pre_signature, signature = text.split('\n-- \n')
            md = markdown.markdown(pre_signature, output_format="html5")
            md += '\n<div class="signature" style="font-size: small"><p>-- <br />'
            md += '<br />'.join(signature.split('\n'))
            md += '</p></div>'
        else:
            md = markdown.markdown(text)
        if config.css:
            md = '<style>' + config.css + '</style>' + md
            md = pynliner.fromString(md)
        message = MIMEText(md, 'html', _charset="UTF-8")
        return message
    except Exception:
        raise
        return None


def _move_headers(source, dest):
    for k, v in source.items():
        # mutt sometimes sticks in a fake bcc header
        if k.lower() == 'bcc':
            del source[k]
        elif not (k.startswith('Content-') or k.startswith('MIME')):
            dest.add_header(k, v)
            del source[k]


def convert_tree(message, config, indent=0):
    """Recursively convert a potentially-multipart tree.

    Returns a tuple of (the converted tree, whether any markdown was found)
    """
    ct = message.get_content_type()
    cs = message.get_content_subtype()
    if not message.is_multipart():
        # we're on a leaf
        converted = None
        disposition = message.get('Content-Disposition', 'inline')
        if disposition == 'inline' and ct in ('text/plain', 'text/markdown'):
            converted = convert_one(message, config)
        if converted is not None:
            new_tree = MIMEMultipart('alternative')
            _move_headers(message, new_tree)
            new_tree.attach(message)
            new_tree.attach(converted)
            return new_tree, True
        return message, False
    else:
        if ct == 'multipart/signed':
            # if this is a multipart/signed message, then let's just
            # recurse into the non-signature part
            for part in message.get_payload():
                if part.get_content_type() != 'application/pgp-signature':
                    return convert_tree(part, config, indent=indent + 1)
        else:
            did_conversion = False
            new_root = MIMEMultipart(cs, message.get_charset())
            if message.preamble:
                new_root.preamble = message.preamble
            _move_headers(message, new_root)
            for part in message.get_payload():
                part, did_this_conversion = convert_tree(part, config, indent=indent + 1)
                did_conversion |= did_this_conversion
                new_root.attach(part)
            return new_root, did_conversion


def process_message(mail, config):
    converted, did_any_markdown = convert_tree(mail, config)
    if 'Bcc' in converted:
        del converted['Bcc']
    return converted


def smtp_connection(c):
    """Create an SMTP connection from a Config object"""
    if c.smtp_ssl:
        klass = smtplib.SMTP_SSL
    else:
        klass = smtplib.SMTP
    conn = klass(c.smtp_host, c.smtp_port, timeout=c.smtp_timeout)
    if not c.smtp_ssl:
        conn.ehlo()
        conn.starttls()
    if c.smtp_username:
        conn.login(c.smtp_username, c.smtp_password)
    return conn


def main():
    parser = argparse.ArgumentParser(prog='muttdown')
    parser.add_argument('-v', '--version', action='version', version='%s %s' % (__name__, __version__))
    parser.add_argument(
        '-c', '--config_file', default=os.path.expanduser('~/.muttdown.yaml'),
        type=argparse.FileType('r'), required=False,
        help='Path to YAML config file (default %(default)s)'
    )
    parser.add_argument(
        '-p', '--print-message', action='store_true',
        help='Print the translated message to stdout instead of sending it'
    )
    parser.add_argument('-f', '--envelope-from', required=True)
    parser.add_argument(
        '-s', '--sendmail-passthru', action='store_true',
        help='Pass mail through to sendmail for delivery'
    )
    parser.add_argument('addresses', nargs='+')
    args = parser.parse_args()

    c = config.Config()
    try:
        c.load(args.config_file)
    except config.ConfigError as e:
        sys.stderr.write('Error(s) in configuration %s:\n' % args.config_file.name)
        sys.stderr.write(' - %s\n' % e.message)
        sys.stderr.flush()
        return 1

    message = sys.stdin.read()

    mail = email.message_from_string(message)

    rebuilt = process_message(mail, c)
    rebuilt.set_unixfrom(args.envelope_from)

    if args.print_message:
        print(rebuilt.as_string())
    elif args.sendmail_passthru:
        cmd = c.sendmail.split() + ['-f', args.envelope_from] + args.addresses

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
        proc.communicate(rebuilt.as_string())
        return proc.returncode
    else:
        conn = smtp_connection(c)
        conn.sendmail(args.envelope_from, args.addresses, rebuilt.as_string())
        conn.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
