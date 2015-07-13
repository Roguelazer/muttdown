muttdown
========

`muttdown` is a sendmail-replacement designed for use with the [mutt][] email client which will transparently compile annotated `text/plain` mail into `text/html` using the [Markdown][] standard.  It will recursively walk the MIME tree and compile any `text/plain` or `text/markdown` part which begins with the sigil "!m" into Markdown, which it will insert alongside the original in a multipart/alternative container.

It's also smart enough not to break `multipart/signed`.

For example, the following tree before parsing:

    - multipart/mixed
     |
     -- multipart/signed
     |
     ---- text/markdown
     |
     ---- application/pgp-signature
     |
     -- image/png

Will get compiled into

    - multipart/mixed
     |
     -- multipart/alternative
     |
     ---- text/html
     |
     ---- multipart/signed
     |
     ------ text/markdown
     |
     ------ application/pgp-signature
     |
     -- image/png


Configuration
-------------
Muttdown's configuration file is written using [YAML][]. Example:

    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_ssl: false
    smtp_username: foo@bar.com
    smtp_password: foo
    css_file: ~/.muttdown.css


If you prefer not to put your password in plaintext in a configuration file, you can instead specify the `smtp_password_command` parameter to invoke a shell command to lookup your password. The command should output your password, followed by a newline, and no other text. On OS X, the following invocation will extract a generic "Password" entry with the application set to "mutt" and the title set to "foo@bar.com":

    smtp_password_command: security find-generic-password -w -s mutt -a foo@bar.com

NOTE: If `smtp_ssl` is set to False, `muttdown` will do a non-SSL session and then invoke `STARTTLS`. If `smtp_ssl` is set to True, `muttdown` will do an SSL session from the get-go. There is no option to send mail in plaintext.

The `css_file` should be regular CSS styling blocks; we use [pynliner][] to inline all CSS rules for maximum client compatibility.

Muttdown can also send its mail using the native `sendmail` if you have that set up (instead of doing SMTP itself). To do so, just leave the smtp options in the config file blank, set the `sendmail` option to the fully-qualified path to your `sendmail` binary, and run muttdown with the `-s` flag

Installation
------------
Install muttdown with `pip install muttdown` or by downloading this package and running `python setup.py install`. You will need the [PyYAML][] and [Python-Markdown][] libraries, as specified in `requirements.txt`.

Usage
-----
Invoke as

    muttdown -c /path/to/config -f "from_address" -- "to_address" [more to addresses...]

Send a RFC822 formatted mail on stdin.

If the config path is not passed, it will assume `~/.muttdown.yaml`.




[Markdown]: http://daringfireball.net/projects/markdown/
[YAML]: http://yaml.org
[PyYAML]: http://pyyaml.org
[Python-Markdown]: https://pypi.python.org/pypi/Markdown
[mutt]: http://www.mutt.org
[pynliner]: https://github.com/rennat/pynliner
