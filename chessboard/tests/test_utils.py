# pylint: disable=C0103,R0904,W0212

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

"""Tests for the :mod:`chessboard.utils` module."""

import copy
import os
import re
import shutil
import time
import tempfile
import unittest
import uuid

import mock

from chessboard import utils


class TestUtils(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils` module."""

    def test_extract_sensitive_data_simple(self):
        fxn = utils.extract_sensitive_data
        self.assertEqual(fxn({}), ({}, None))
        combined = {
            'innocuous': 'Hello!',
            'password': 'secret',
        }
        innocuous = {'innocuous': 'Hello!'}
        secret = {'password': 'secret'}
        original = copy.copy(combined)
        self.assertEqual(fxn(combined, sensitive_keys=[]), (combined, None))
        self.assertEqual(fxn(combined, ['password']), (innocuous, secret))
        self.assertDictEqual(combined, original)

    def test_extract_sensitive_data_works_with_None_keys(self):
        sensitive_keys = [re.compile('quux')]
        data = {None: 'foobar'}
        expected = (data, None)
        self.assertEqual(expected,
                         utils.extract_sensitive_data(data, sensitive_keys))

    def test_flatten(self):
        list_of_dict = [{'foo': 'bar'}, {'a': 'b'}, {'foo': 'bar1'}]
        self.assertDictEqual(utils.flatten(list_of_dict),
                             {'foo': 'bar1', 'a': 'b'})

    def test_extract_data_expression_as_sensitive(self):
        data = {
            "employee": {
                "name": "Bob",
                "title": "Mr.",
                "public_key": "rsa public key",
                "private_key": "a private key",
                "password": "password",
                "position": "left"
            },
            "server": {
                "access": {
                    "rootpassword": "password",
                    "server_privatekey": "private_key",
                    "server_public_key": "public_key"
                },
                "private_ip": "123.45.67.89",
                "public_ip": "127.0.0.1",
                "host_name": "server1"
            },
            "safe_val": "hithere",
            "secret_value": "Immasecret"
        }

        safe = {
            "employee": {
                "name": "Bob",
                "title": "Mr.",
                "public_key": "rsa public key",
                "position": "left"
            },
            "server": {
                "access": {
                    "server_public_key": "public_key"
                },
                "private_ip": "123.45.67.89",
                "public_ip": "127.0.0.1",
                "host_name": "server1"
            },
            "safe_val": "hithere",
        }

        secret = {
            "employee": {
                "private_key": "a private key",
                "password": "password",
            },
            "server": {
                "access": {
                    "rootpassword": "password",
                    "server_privatekey": "private_key",
                }
            },
            "secret_value": "Immasecret"
        }

        original_dict = copy.deepcopy(data)
        secret_keys = ["secret_value", re.compile("password"),
                       re.compile("priv(?:ate)?[-_ ]?key$")]
        body, hidden = utils.extract_sensitive_data(data, secret_keys)
        self.assertDictEqual(body, safe)
        self.assertDictEqual(secret, hidden)
        utils.merge_dictionary(body, hidden)
        self.assertDictEqual(original_dict, body)

    def test_extract_sensitive_data_complex(self):
        fxn = utils.extract_sensitive_data
        self.assertEqual(fxn({}), ({}, None))
        combined = {
            'innocuous': {
                'names': ['Tom', 'Richard', 'Harry']
            },
            'data': {
                'credentials': [{'password': 'secret', 'username': 'joe'}],
                'id': 1000,
                'list_with_only_cred_objects': [{'password': 'secret'}],
                'list_with_some_cred_objects': [
                    {
                        'password': 'secret',
                        'type': 'password',
                    },
                    'scalar',
                    {'name': 'joe'}
                ]
            }
        }
        innocuous = {
            'innocuous': {
                'names': ['Tom', 'Richard', 'Harry']
            },
            'data': {
                'id': 1000,
                'list_with_some_cred_objects': [
                    {
                        'type': 'password'
                    },
                    'scalar',
                    {'name': 'joe'}
                ]
            }
        }
        secret = {
            'data': {
                'credentials': [{'password': 'secret', 'username': 'joe'}],
                'list_with_only_cred_objects': [{'password': 'secret'}],
                'list_with_some_cred_objects': [
                    {
                        'password': 'secret'
                    },
                    None,
                    {}
                ]
            }
        }
        original = copy.copy(combined)
        not_secret, is_secret = fxn(combined, [])
        self.assertDictEqual(not_secret, combined)
        self.assertIsNone(is_secret)

        not_secret, is_secret = fxn(combined, ['credentials', 'password'])
        self.assertDictEqual(not_secret, innocuous)
        self.assertDictEqual(is_secret, secret)
        self.assertDictEqual(combined, original)

        merged = utils.merge_dictionary(innocuous, secret)
        self.assertDictEqual(original, merged)

    def test_default_secrets_detected(self):
        data = {
            'apikey': 'secret',
            'error-string': 'secret',
            'error-traceback': 'secret',
            'password': 'secret',
        }
        body, hidden = utils.extract_sensitive_data(data)
        self.assertIsNone(body)
        self.assertEqual(hidden, data)

    def test_extract_and_merge(self):
        fxn = utils.extract_sensitive_data
        data = {
            'empty_list': [],
            'empty_object': {},
            'null': None,
            'list_with_empty_stuff': [{}, None, []],
            'object_with_empty_stuff': {"o": {}, "n": None, 'l': []},
            "tree": {
                "array": [
                    {
                        "blank": {},
                        "scalar": 1
                    }
                ]
            }
        }
        result, _ = fxn(data, [])
        self.assertDictEqual(data, result)
        merge = utils.merge_dictionary(data, data)
        self.assertDictEqual(data, merge)
        merge = utils.merge_dictionary(data, {})
        self.assertDictEqual(data, merge)
        merge = utils.merge_dictionary({}, data)
        self.assertDictEqual(data, merge)

    def test_merge_dictionary(self):
        dst = dict(a=1, b=2, c=dict(ca=31, cc=33, cd=dict(cca=1)), d=4, f=6,
                   g=7, i=[], k=[3, 4], l=[[], [{'s': 1}]])
        src = dict(b='u2', c=dict(cb='u32', cd=dict(cda=dict(cdaa='u3411',
                   cdab='u3412'))), e='u5', h=dict(i='u4321'), i=[1], j=[1, 2],
                   l=[None, [{'t': 8}]])
        result = utils.merge_dictionary(dst, src)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['a'], 1)
        self.assertEqual(result['d'], 4)
        self.assertEqual(result['f'], 6)
        self.assertEqual(result['b'], 'u2')
        self.assertEqual(result['e'], 'u5')
        self.assertIs(result['c'], dst['c'])
        self.assertIs(result['c']['cd'], dst['c']['cd'])
        self.assertEqual(result['c']['cd']['cda']['cdaa'], 'u3411')
        self.assertEqual(result['c']['cd']['cda']['cdab'], 'u3412')
        self.assertEqual(result['g'], 7)
        self.assertIs(src['h'], result['h'])
        self.assertEqual(result['i'], [1])
        self.assertEqual(result['j'], [1, 2])
        self.assertEqual(result['k'], [3, 4])
        self.assertEqual(result['l'], [[], [{'s': 1, 't': 8}]])

    def test_merge_lists(self):
        dst = [[], [2], [None, 4]]
        src = [[1], [], [3, None]]
        result = utils.merge_lists(dst, src)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], [1])
        self.assertEqual(result[1], [2])
        self.assertEqual(result[2], [3, 4], "Found: %s" % result[2])

    def test_is_ssh_key(self):
        self.assertFalse(utils.is_ssh_key(None))
        self.assertFalse(utils.is_ssh_key(''))
        self.assertFalse(utils.is_ssh_key(1))
        self.assertFalse(utils.is_ssh_key("AAAAB3NzaC1yc2EA"))
        self.assertFalse(utils.is_ssh_key("AAAAB3NzaC1yc2EA-bad"))
        self.assertFalse(utils.is_ssh_key("AAAAB3NzaC1yc2EA onespace"))
        self.assertFalse(utils.is_ssh_key("AAAAB3NzaC1yc2EA two space"))
        self.assertFalse(utils.is_ssh_key("AAAAB3NzaC1yc2EA 3 spaces here"))
        key = ("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDtjYYMFbpCJ/ND3izZ1DqNFQ"
               "HlooXyNcDGWilAqNqcCfz9L+gpGjY2pQlZz/1Hir3R8fz0MS9VY32RYmP3wWyg"
               "t85kNccEkOpVGGpGyV/aMFaQHZD0h6d0AT+haP0Iig+OrH1YBnpdgVPWx3SbU4"
               "eV/KYGpO9Mintj3P54of22lTK4dOwCNvID9P9w+T1kMfdVxGwhqsSL0RxVXnSS"
               "kozXQWCNvaZJMUmidm8YA009c5PoksyWjl3EE+rEzZ8ywvtUJf9DvnLCESfhF3"
               "hK5lAiEd8z7gyiQnBexn/dXzldGFiJYJgQ5HolYaNMtTF+AQY6R6Qt0okCPyED"
               "JxHJUM7d")
        self.assertTrue(utils.is_ssh_key(key))
        self.assertTrue(utils.is_ssh_key("%s /n" % key))
        self.assertTrue(utils.is_ssh_key("%s email@domain.com/n" % key))
        key = ("ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7TT1qbLElv6tuAaA3Z4tQ752ms"
               "0Y7H53yybfFioFHELkp+NRMCKh4AqtqDBFsps1vPzhcXIxn4M4IH0ip7kSx0CS"
               "rM/9Vtz8jc+UZwixJdAWwHpum68rGmCQgAsZljI24Q9u8r/hXqjwY6ukTKbC0i"
               "y82LHqhcDjh3828+9GyyxbYGm5ND/5G/ZcnHD6HM9YKmc3voz5d/nez3Adlu4I"
               "1z4Y1T3lOwOxrP2OqvIeDPvVOZJ9GDmYYRDfqK8OIHDoLAzQx8xu0cvPRDL7gY"
               "RXN8nJZ5nOh+51zdPQEl99ACZDSSwTl2biOPNtXtuaGyjB5j8r7dz93JlsN8ax"
               "eD+ECQ== ziad@sawalha.com")
        self.assertTrue(utils.is_ssh_key(key))

    def test_get_source_body(self):
        source = utils.get_source_body(self.test_get_source_body)
        self.assertTrue(source.startswith("source = utils"))

        source = utils.get_source_body(self.dummy_static)
        self.assertTrue(source.startswith('"""Used for get_source_body'))

    @staticmethod
    def dummy_static():
        """Used for get_source_body test."""
        pass

    def test_is_uuid_blanks(self):
        self.assertFalse(utils.is_uuid(None), "None is not a UUID")
        self.assertFalse(utils.is_uuid(""), "Empty string is not a UUID")
        self.assertFalse(utils.is_uuid(" "), "Space is not a UUID")

    def test_is_uuid_negatives(self):
        self.assertFalse(utils.is_uuid("12345"), "12345 is not a UUID")
        self.assertFalse(utils.is_uuid(utils), "module is not a UUID")

    def test_is_uuid_positives(self):
        self.assertTrue(utils.is_uuid(uuid.uuid4()), "uuid() is a UUID")
        self.assertTrue(utils.is_uuid(uuid.uuid4().hex),
                        "uuid string is a UUID")

    def test_write_path(self):
        cases = [
            {
                'name': 'scalar at root',
                'start': {},
                'path': 'root',
                'value': 'scalar',
                'expected': {'root': 'scalar'}
            }, {
                'name': 'int at root',
                'start': {},
                'path': 'root',
                'value': 10,
                'expected': {'root': 10}
            }, {
                'name': 'bool at root',
                'start': {},
                'path': 'root',
                'value': True,
                'expected': {'root': True}
            }, {
                'name': 'value at two piece path',
                'start': {},
                'path': 'root/subfolder',
                'value': True,
                'expected': {'root': {'subfolder': True}}
            }, {
                'name': 'value at multi piece path',
                'start': {},
                'path': 'one/two/three',
                'value': {},
                'expected': {'one': {'two': {'three': {}}}}
            }, {
                'name': 'add to existing',
                'start': {'root': {'exists': True}},
                'path': 'root/new',
                'value': False,
                'expected': {'root': {'exists': True, 'new': False}}
            }, {
                'name': 'overwrite existing',
                'start': {'root': {'exists': True}},
                'path': 'root/exists',
                'value': False,
                'expected': {'root': {'exists': False}}
            }
        ]
        for case in cases:
            result = case['start']
            utils.write_path(result, case['path'], case['value'])
            self.assertDictEqual(result, case['expected'], msg=case['name'])

    def test_read_path(self):
        cases = [
            {
                'name': 'simple value',
                'start': {'root': 1},
                'path': 'root',
                'expected': 1
            }, {
                'name': 'simple path',
                'start': {'root': {'folder': 2}},
                'path': 'root/folder',
                'expected': 2
            }, {
                'name': 'blank path',
                'start': {'root': 1},
                'path': '',
                'expected': None
            }, {
                'name': '/ only',
                'start': {'root': 1},
                'path': '/',
                'expected': None
            }, {
                'name': 'extra /',
                'start': {'root': 1},
                'path': '/root/',
                'expected': 1
            }, {
                'name': 'nonexistent root',
                'start': {'root': 1},
                'path': 'not-there',
                'expected': None
            }, {
                'name': 'nonexistent path',
                'start': {'root': 1},
                'path': 'root/not-there',
                'expected': None
            }, {
                'name': 'empty source',
                'start': {},
                'path': 'root',
                'expected': None
            },
        ]
        for case in cases:
            result = utils.read_path(case['start'], case['path'])
            self.assertEqual(result, case['expected'], msg=case['name'])

    def test_path_exists(self):
        cases = [
            {
                'name': 'simple value',
                'start': {'root': 1},
                'path': 'root',
                'expected': True
            }, {
                'name': 'simple path',
                'start': {'root': {'folder': 2}},
                'path': 'root/folder',
                'expected': True
            }, {
                'name': 'blank path',
                'start': {'root': 1},
                'path': '',
                'expected': False
            }, {
                'name': '/ only',
                'start': {'root': 1},
                'path': '/',
                'expected': True
            }, {
                'name': 'extra /',
                'start': {'root': 1},
                'path': '/root/',
                'expected': True
            }, {
                'name': 'nonexistent root',
                'start': {'root': 1},
                'path': 'not-there',
                'expected': False
            }, {
                'name': 'nonexistent path',
                'start': {'root': 1},
                'path': 'root/not-there',
                'expected': False
            }, {
                'name': 'empty source',
                'start': {},
                'path': 'root',
                'expected': False
            },
        ]
        for case in cases:
            result = utils.path_exists(case['start'], case['path'])
            self.assertEqual(result, case['expected'], msg=case['name'])

    def test_is_evaluable(self):
        self.assertTrue(utils.is_evaluable('=generate_password()'))
        self.assertTrue(utils.is_evaluable('=generate_uuid()'))
        self.assertFalse(utils.is_evaluable('=generate_something_else()'))
        self.assertFalse(utils.is_evaluable({'not-a-string': 'boom!'}))

    def test_get_formatted_time_string(self):
        some_time = time.gmtime(0)
        with mock.patch.object(utils.time, 'gmtime') as mock_gmt:
            mock_gmt.return_value = some_time
            result = utils.get_time_string()
            self.assertEqual(result, "1970-01-01 00:00:00 +0000")

    def test_get_formatted_time_string_with_input(self):
        result = utils.get_time_string(time_gmt=time.gmtime(0))
        self.assertEqual(result, "1970-01-01 00:00:00 +0000")

    def test_generate_password(self):
        password = utils.evaluate('generate_password()')
        self.assertEqual(12, len(password))

    def test_generate_8_character_password(self):
        password = utils.evaluate('generate_password(min_length=8)')
        self.assertEqual(8, len(password))

    def test_escape_yaml_simple_string_simple(self):
        self.assertEqual(utils.escape_yaml_simple_string('simple'), "simple")

    def test_escape_yaml_simple_string_null(self):
        self.assertEqual(utils.escape_yaml_simple_string(None), 'null')

    def test_escape_yaml_simple_string_blank(self):
        self.assertEqual(utils.escape_yaml_simple_string(''), "''")

    def test_escape_yaml_simple_string_at(self):
        self.assertEqual(utils.escape_yaml_simple_string("@starts_with_at"),
                         "'@starts_with_at'")

    def test_escape_yaml_simple_string_multi_line(self):
        self.assertEqual(utils.escape_yaml_simple_string('A\nB'), 'A\nB')

    def test_escape_yaml_simple_string_object(self):
        self.assertEqual(utils.escape_yaml_simple_string({'A': 1}), {'A': 1})

    def test_hide_url_password(self):
        hidden = utils.hide_url_password('http://user:pass@localhost')
        self.assertEqual(hidden, 'http://user:*****@localhost')

    def test_hide_url_password_mongo(self):
        hidden = utils.hide_url_password('mongodb://user:pass@localhost/db')
        self.assertEqual(hidden, 'mongodb://user:*****@localhost/db')


class TestSetUrlCreds(unittest.TestCase):

    def test_set_empty(self):
        url = utils.set_url_creds("http://usr:px@fqdn:80/path#fr?q=1")
        self.assertEqual(url, "http://fqdn:80/path#fr?q=1")

    def test_set_username(self):
        url = utils.set_url_creds("http://usr:px@fqdn/path#fr?q=1",
                                  username="new")
        self.assertEqual(url, "http://new@fqdn/path#fr?q=1")

    def test_set_password(self):
        url = utils.set_url_creds("http://usr:px@fqdn/path#fr?q=1",
                                  password="new")
        self.assertEqual(url, "http://new@fqdn/path#fr?q=1")

    def test_set_both(self):
        url = utils.set_url_creds("http://usr:px@fqdn/path#fr?q=1",
                                  password="new", username="bob")
        self.assertEqual(url, "http://bob:new@fqdn/path#fr?q=1")


class TestDirComparison(unittest.TestCase):

    def setUp(self):
        dir1 = tempfile.mkdtemp()
        subdir1 = os.path.join(dir1, 'subdir')
        os.mkdir(subdir1)
        file1 = os.path.join(dir1, 'foo.txt')
        with open(file1, 'w') as fh1:
            fh1.write('Hi!')

        dir2 = tempfile.mkdtemp()
        subdir2 = os.path.join(dir2, 'subdir')
        os.mkdir(subdir2)
        file2 = os.path.join(dir2, 'foo.txt')
        with open(file2, 'w') as fh2:
            fh2.write('Hi!')

        self.dir1 = dir1
        self.subdir1 = subdir1
        self.file1 = file1
        self.dir2 = dir2
        self.subdir2 = subdir2
        self.file2 = file2

    def tearDown(self):
        try:
            shutil.rmtree(self.dir1)
        except OSError:
            assert not os.path.exists(self.dir1)
        try:
            shutil.rmtree(self.dir2)
        except OSError:
            assert not os.path.exists(self.dir2)

    def test_positive(self):
        self.assertTrue(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_missing_dir1_fails(self):
        shutil.rmtree(self.dir1)
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_missing_dir2_fails(self):
        shutil.rmtree(self.dir2)
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_extra_dir_left_fails(self):
        os.mkdir(os.path.join(self.dir1, 'extra'))
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_extra_dir_right_fails(self):
        os.mkdir(os.path.join(self.dir2, 'extra'))
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_extra_file_left_fails(self):
        with open(os.path.join(self.dir1, 'extra.txt'), 'w') as extra:
            extra.write("Irrelevant")
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_extra_file_right_fails(self):
        with open(os.path.join(self.dir2, 'extra.txt'), 'w') as extra:
            extra.write("Irrelevant")
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))

    def test_file_content_fails(self):
        with open(os.path.join(self.dir1, 'readme.txt'), 'w') as extra:
            extra.write("pip install")
        with open(os.path.join(self.dir2, 'readme.txt'), 'w') as extra:
            extra.write("pip uninstall")
        self.assertFalse(utils.are_dir_trees_equal(self.dir1, self.dir2))


if __name__ == '__main__':
    unittest.main()
