import copy
import yaml
import subprocess

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
        for parameter in cls._parameters.iterkeys():
            if parameter not in d:
                f = _param_getter_factory(parameter)
                setattr(cls, parameter, property(f))
        return cls


class ConfigError(Exception):
    def __init__(self, message):
        self.message = message


class Config(object):
    __metaclass__ = _ParamsAsProps

    _parameters = {
        'smtp_host': '127.0.0.1',
        'smtp_port': 25,
        'smtp_ssl': True,  # if false, do STARTTLS
        'smtp_username': '',
        'smtp_password': None,
        'smtp_password_command': None,
        'smtp_timeout': 10
    }

    def __init__(self):
        self._config = copy.copy(self._parameters)

    def merge_config(self, d):
        invalid_keys = set(d.keys()) - set(self._config.keys())
        if invalid_keys:
            raise ConfigError('Unexpected config keys: %s' % ', '.join(sorted(invalid_keys)))
        for key in self._config:
            if key in d:
                self._config[key] = d[key]
        if self._config['smtp_password'] and self._config['smtp_password_command']:
            raise ConfigError('Cannot set smtp_password *and* smtp_password_command')

    def load(self, fobj):
        d = yaml.safe_load(fobj)
        self.merge_config(d)

    @property
    def smtp_password(self):
        if self._config['smtp_password_command']:
            return check_output(self._config['smtp_password_command'], shell=True).rstrip('\n')
        else:
            return self._config['smtp_password']
