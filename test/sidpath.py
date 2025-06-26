from abc import abstractmethod
from collections import abc
import json
import os
import unittest
import subprocess

import psycopg
from psycopg.sql import SQL

from cqi.sidepath import SidepathDictEntry
from cqi.util import unwrap

class SidepathEntryTest:
    @abstractmethod
    def assert_is_sidepath(self, expected: bool, entry: dict):
        raise Exception('abstract method not implemented')

    def test_is_sidepath__id_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 2, 'id': {'id1': 2} }
        )

    def test_is_sidepath__id_2(self):
        self.assert_is_sidepath(
           False,
          { 'checks': 2, 'id': {'id1': 1} }
        )

    def test_is_sidepath__id_3(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 6, 'id': {'id1': 1, 'id2': 4} }
        )

    def test_is_sidepath__id_4(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 6, 'id': {'id1': 2, 'id2': 2} },
        )

    def test_is_sidepath__highway_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 2, 'highway': {'id1': 2} }
        )

    def test_is_sidepath__highway_2(self):
        self.assert_is_sidepath(
           False,
          { 'checks': 2, 'highway': {'id1': 1} }
        )

    def test_is_sidepath__highway_3(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 6, 'highway': {'id1': 1, 'id2': 4} }
        )

    def test_is_sidepath__highway_4(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 6, 'highway': {'id1': 2, 'id2': 2} },
        )


    def test_is_sidepath__name_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 2, 'name': {'id1': 2} }
        )

    def test_is_sidepath_name_2(self):
        self.assert_is_sidepath(
           False,
          { 'checks': 2, 'name': {'id1': 1} }
        )

    def test_is_sidepath__name_3(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 6, 'name': {'id1': 1, 'id2': 4} }
        )

    def test_is_sidepath__name_4(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 6, 'name': {'id1': 2, 'id2': 2} },
        )

        
    def test_is_sidepath__id_name_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'name': {'n1': 2}, 'id': {'i1': 1} }
        )

    def test_is_sidepath__id_name_2(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'name': {'n1': 1}, 'id': {'i1': 2} }
        )

    def test_is_sidepath__id_name_3(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 3, 'name': {'n1': 1}, 'id': {'i1': 1} }
        )

    def test_is_sidepath__id_highway_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'highway': {'h1': 2}, 'id': {'i1': 1} }
        )

    def test_is_sidepath__id_highway_2(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'highway': {'h1': 1}, 'id': {'i1': 2} }
        )

    def test_is_sidepath__id_highway_3(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 3, 'highway': {'h1': 1}, 'id': {'i1': 1} }
        )

    def test_is_sidepath__name_highway_1(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'highway': {'h1': 1}, 'name': {'n1': 2} }
        )

    def test_is_sidepath__name_highway_2(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'highway': {'h1': 2}, 'name': {'n1': 1} }
        )

    def test_is_sidepath__name_highway_3(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 3, 'highway': {'h1': 1}, 'name': {'n1': 1} }
        )


    def test_is_sidepath__id_name_highway_1(self):
        self.assert_is_sidepath(
           False,
           { 'checks': 3, 'name': {'id1': 1}, 'highway': { 'h1': 1 }, 'id': {'i1': 1} }
        )

    def test_is_sidepath__id_name_highway_2(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'name': {'id1': 2}, 'highway': { 'h1': 1 }, 'id': {'i1': 1} }
        )
    def test_is_sidepath__id_name_highway_3(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'name': {'id1': 1}, 'highway': { 'h1': 2 }, 'id': {'i1': 1} }
        )
    def test_is_sidepath__id_name_highway_4(self):
        self.assert_is_sidepath(
           True,
           { 'checks': 3, 'name': {'id1': 1}, 'highway': { 'h1': 1 }, 'id': {'i1': 2} }
        )

class CqilibSidepathEntryTest(unittest.TestCase, SidepathEntryTest):

    def assert_is_sidepath(self, expected: bool, entry: dict):
        self.assertEqual(SidepathDictEntry.from_dict(entry).is_sidepath(), expected)

db_url = os.getenv('GEO_DATABASE_URL')

@unittest.skipIf(db_url is None, 'GEO_DATABASE_URL not set, skipping postgres tests')
class SqlSidepathEntryTest(unittest.TestCase, SidepathEntryTest):

    @classmethod
    def setUpClass(cls):
        subprocess.run(['psql', unwrap(db_url), '-f', 'sql/sidepath_lib.sql'], check=True)
    
    def setUp(self) -> None:
        self.conn = psycopg.connect(unwrap(db_url))

    def tearDown(self) -> None:
        self.conn.close()

    def assert_is_sidepath(self, expected: bool, entry: dict):
        entry_json = json.dumps(entry)
        result = unwrap(self.conn.execute('SELECT sidepath_dict_is_sidepath(%s::jsonb)', [entry_json]).fetchone())[0]
        self.assertEqual(result, expected)

if __name__ == 'main':
    unittest.main()
