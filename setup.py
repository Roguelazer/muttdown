#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name="muttdown",
    version="0.3.1",
    author="James Brown",
    author_email="Roguelazer@gmail.com",
    url="https://github.com/Roguelazer/muttdown",
    license="ISC",
    packages=find_packages(exclude=['tests']),
    keywords=["email"],
    description="Sendmail replacement that compiles markdown into HTML",
    install_requires=[
        'Markdown>=2.0',
        'PyYAML>=3.0',
        'pynliner==0.8.0',
        'six',
    ],
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
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Topic :: Communications :: Email",
    ]
)
