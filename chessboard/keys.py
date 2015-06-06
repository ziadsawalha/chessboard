# Copyright 2015 Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Key management module."""

import logging

from Crypto.PublicKey import RSA  # pip install pycrypto
from Crypto import Random
from passlib.hash import md5_crypt
from passlib.hash import sha512_crypt


LOG = logging.getLogger(__name__)


def generate_key_pair(bits=2048):
    """Generate a private/public key pair.

    :returns: private, public tuple of dicts. The dicts have key,
    and PEM values. The public key also has an ssh value in it
    """
    Random.atfork()
    key = RSA.generate(bits)
    private_string = key.exportKey('PEM')
    public = key.publickey()
    public_string = public.exportKey('PEM')
    ssh = public.exportKey('OpenSSH')
    return (dict(key=key, PEM=private_string),
            dict(key=public, PEM=public_string, ssh=ssh))


def get_ssh_public_key(private_key):
    """Generate an ssh public key from a private key string."""
    key = RSA.importKey(private_key)
    return key.publickey().exportKey('OpenSSH')


def get_public_key(private_key):
    """Generate a PEM public key from a private key string."""
    key = RSA.importKey(private_key)
    return key.publickey().exportKey('PEM')


def hash_SHA512(value, salt=None):
    """Create random SHA512 hashed value."""
    if not salt:
        return sha512_crypt.encrypt(value)
    return sha512_crypt.encrypt(value, salt=salt)


def hash_MD5(value, salt=None):
    """Create random MD5 hashed value."""
    if not salt:
        return md5_crypt.encrypt(value)
    return md5_crypt.encrypt(value, salt=salt)
