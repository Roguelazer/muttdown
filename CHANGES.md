0.3.5
=====
- Fix some unicode handling (including, hopefully, fixing non-ASCII subject lines for real)
- Drops support for Python 3.3 and Python 3.4 since we depend on libraries that have dropped support for them
- Add support for Python 3.7 and Python 3.8

0.3.4
=====
- Fix regression in headers from 0.3.0 with some multipart/signed messages
- Fix regression in passthrough mode from 0.3.3 on Python 2; add better testing

0.3.3
=====
- Fix `-s` / smtp passthrough mode on Python 3

0.3.2
=====
- Fix `smtp_password_command`
- Fix tests with newer version of pytest

0.3.1
=====
- Fix an incompatibility with Python 3.5

0.3
===
- Add a man page (contribution by @ssgelm)
- Split `sendmail` command on whitespace (contribution by @nottwo)
- Fix a ton of bugs with MIME tree construction
- fix tests
