"""Chessboard: Describe an application once, deploy and manage it anywhere.

Chessboard includes utilities for modeling application topologies and
deploying/managing applications in a provider-agnostic way.
"""

import setuptools


VERSION = '0.1.0'

setuptools.setup(
    name='chessboard',
    version=VERSION,
    maintainer='Rackspace Hosting, Inc.',
    url='https://github.com/checkmate/chessboard',
    description='Describe an application once, deploy and manage it anywhere',
    platforms=['any'],
    packages=setuptools.find_packages(
        exclude=['chessboard.tests', 'chessboard.tests.*']
    ),
    provides=['chessboard (%s)' % VERSION],
    license='Apache License 2.0',
    keywords=(
        'application model topology deployment manage orchestration '
        'configuration automation checkmate'
    ),
    include_package_data=True,
    data_files=[('chessboard', ['chessboard/schema_docs.yaml'])],
    classifiers=(
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development',
        'Topic :: System :: Systems Administration',
    ),
)
