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

import markdown
import pynliner

from . import config
from . import __version__

__name__ = 'muttdown'


def convert_one(part, config):
    try:
        text = part.get_payload(None, True)
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
        message = MIMEText(md, 'html')
        return message
    except Exception:
        return None


def convert_tree(message, config):
    """Recursively convert a potentially-multipart tree.

    Returns a tuple of (the converted tree, whether any markdown was found)
    """
    ct = message.get_content_type()
    if message.is_multipart():
        if ct == 'multipart/signed':
            # if this is a multipart/signed message, then let's just
            # recurse into the non-signature part
            for part in message.get_payload():
                if part.get_content_type() != 'application/pgp-signature':
                    return convert_tree(part, config)
        else:
            # it's multipart, but not signed. copy it!
            new_root = MIMEMultipart(message.get_content_subtype(), message.get_charset())
            did_conversion = False
            for part in message.get_payload():
                converted_part, this_did_conversion = convert_tree(part, config)
                did_conversion |= this_did_conversion
                new_root.attach(converted_part)
            return new_root, did_conversion
    else:
        # okay, this isn't a multipart type. If it's inline
        # and it's either text/plain or text/markdown, let's convert it
        converted = None
        disposition = message.get('Content-Disposition', 'inline')
        if disposition == 'inline' and ct in ('text/plain', 'text/markdown'):
            converted = convert_one(message, config)
        if converted is not None:
            return converted, True
        return message, False


def rebuild_multipart(mail, config):
    converted, did_any_markdown = convert_tree(mail, config)
    if did_any_markdown:
        new_top = MIMEMultipart('alternative')
        for k, v in mail.items():
            # the fake Bcc header definitely shouldn't keep existing
            if k.lower() == 'bcc':
                del mail[k]
            elif not (k.startswith('Content-') or k.startswith('MIME')):
                new_top.add_header(k, v)
                del mail[k]
        new_top.attach(mail)
        new_top.attach(converted)
        return new_top
    else:
        return mail


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
    parser = argparse.ArgumentParser(version='%s %s' % (__name__, __version__))
    parser.add_argument(
        '-c', '--config_file', default=os.path.expanduser('~/.muttdown.yaml'),
        type=argparse.FileType('r'), required=True,
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
        print('Error(s) in configuration %s:' % args.config_file.name)
        print(' - ' + e.message)
        return 1

    message = sys.stdin.read()

    mail = email.message_from_string(message)

    rebuilt = rebuild_multipart(mail, c)
    rebuilt.set_unixfrom(args.envelope_from)

    if args.print_message:
        print(rebuilt.as_string())
    elif args.sendmail_passthru:
        cmd = [c.sendmail, '-f', args.envelope_from] + args.addresses

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=False)
        proc.communicate(rebuilt.as_string())

    else:
        conn = smtp_connection(c)
        conn.sendmail(args.envelope_from, args.addresses, rebuilt.as_string())
        conn.quit()

if __name__ == '__main__':
    main()
