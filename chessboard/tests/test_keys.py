# pylint: disable=C0103

# Copyright (c) 2011-2015 Rackspace US, Inc.
# All Rights Reserved.
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Main Tests for the :mod:`chessboard.keys` module."""

import unittest

from chessboard import keys


class TestKeys(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.keys` module."""

    def test_hashSHA512(self):
        hashed_value = keys.hash_SHA512('test', salt="abcdefgh")
        self.assertEqual(hashed_value, '$6$rounds=100000$abcdefgh$Nc/EUrz68.Ae'
                                       'CLHF6f6gQe7e/0a7/k1sf98jrxAajtx20KwiAh'
                                       'thVIFhJ.EQZN5RDxOCAEVmbE3Vb.pRYUmqv1')

    def test_hashMD5(self):
        hashed_value = keys.hash_MD5('test', salt="abcdefgh")
        self.assertEqual(hashed_value, '$1$abcdefgh$irWbblnpmw.5z7wgBnprh0')


if __name__ == '__main__':
    unittest.main()
