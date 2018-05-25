import copy
import yaml
import subprocess
import os.path

import six

# largely copied from my earlier work in fakemtpd


if hasattr(subprocess, 'check_output'):
    check_output = subprocess.check_output
else:
    def check_output(*args, **kwargs):
        kwargs['stdout'] = subprocess.PIPE
        p = subprocess.Popen(*args, **kwargs)
        stdout, _ = p.communicate()
        assert p.returncode == 0
        return stdout


def _param_getter_factory(parameter):
    def f(self):
        return self._config[parameter]
    f.__name__ = parameter
    return f


class _ParamsAsProps(type):
    """Create properties on the classes that apply this for everything
    in cls._parameters which read out of self._config.

    Cool fact: you can override any of these properties by just defining
    your own with the same name. Just like if they were statically defined!"""
    def __new__(clsarg, name, bases, d):
        cls = super(_ParamsAsProps, clsarg).__new__(clsarg, name, bases, d)
        for parameter in cls._parameters.keys():
            if parameter not in d:
                f = _param_getter_factory(parameter)
                setattr(cls, parameter, property(f))
        return cls


class ConfigError(Exception):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.message)

    def __str__(self):
        return '%s(%r)' % (self.__class__.__name__, self.message)


@six.add_metaclass(_ParamsAsProps)
class Config(object):
    _parameters = {
        'smtp_host': '127.0.0.1',
        'smtp_port': 25,
        'smtp_ssl': True,  # if false, do STARTTLS
        'smtp_username': '',
        'smtp_password': None,
        'smtp_password_command': None,
        'smtp_timeout': 10,
        'css_file': None,
        'sendmail': '/usr/sbin/sendmail',
    }

    def __init__(self):
        self._config = copy.copy(self._parameters)
        self._css = None

    def merge_config(self, d):
        invalid_keys = set(d.keys()) - set(self._config.keys())
        if invalid_keys:
            raise ConfigError('Unexpected config keys: %s' % ', '.join(sorted(invalid_keys)))
        for key in self._config:
            if key in d:
                self._config[key] = d[key]
        if self._config['smtp_password'] and self._config['smtp_password_command']:
            raise ConfigError('Cannot set smtp_password *and* smtp_password_command')
        if self._config['css_file']:
            self._config['css_file'] = os.path.expanduser(self._config['css_file'])
            if not os.path.exists(self._config['css_file']):
                raise ConfigError('CSS file %s does not exist' % self._config['css_file'])

    def load(self, fobj):
        d = yaml.safe_load(fobj)
        self.merge_config(d)

    @property
    def css(self):
        if self._css is None:
            if self.css_file is not None:
                with open(os.path.expanduser(self.css_file), 'r') as f:
                    self._css = f.read()
            else:
                self._css = ''
        return self._css

    @property
    def smtp_password(self):
        if self._config['smtp_password_command']:
            return check_output(self._config['smtp_password_command'], shell=True).rstrip('\n')
        else:
            return self._config['smtp_password']
