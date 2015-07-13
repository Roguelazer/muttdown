#!/usr/bin/env python
import collections

from setuptools import setup, find_packages
import pip
from pip.req import parse_requirements


def _version_tuple(version_string):
    return tuple(
        (int(component) if all(x.isdigit() for x in component) else component)
        for component
        in version_string.split('.')
    )


def get_install_requirements():

    ReqOpts = collections.namedtuple(
        'ReqOpts',
        ['skip_requirements_regex', 'default_vcs', 'isolated_mode']
    )

    opts = ReqOpts(None, 'git', False)

    requires = []
    dependency_links = []

    req_args = ['requirements.txt']
    req_kwargs = {'options': opts}

    pip_version_info = _version_tuple(pip.__version__)

    if pip_version_info >= (6, 0):
        from pip.download import PipSession
        session = PipSession()
        req_kwargs['session'] = session

    for ir in parse_requirements(*req_args, **req_kwargs):
        if ir is not None:
            if pip_version_info >= (6, 0):
                if ir.link is not None:
                    dependency_links.append(str(ir.url))
            else:
                if ir.url is not None:
                    dependency_links.append(str(ir.url))
            if ir.req is not None:
                requires.append(str(ir.req))
    return requires, dependency_links


install_requires, dependency_links = get_install_requirements()

setup(
    name="muttdown",
    version="0.2",
    author="James Brown",
    author_email="Roguelazer@gmail.com",
    url="https://github.com/Roguelazer/muttdown",
    license="ISC",
    packages=find_packages(exclude=['tests']),
    keywords=["email"],
    description="Sendmail replacement that compiles markdown into HTML",
    install_requires=install_requires,
    dependency_links=dependency_links,
    test_suite="nose.collector",
    entry_points={
        'console_scripts': [
            'muttdown = muttdown.main:main',
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Topic :: Communications :: Email",
    ]
)
