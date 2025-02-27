"""unittest tests that require a live Drupal at http://localhost:8000. In most cases, the URL, credentials,
   etc. are in a configuration file referenced in the test.

   Files islandora_tests_check.py, islandora_tests_paged_content.py, and islandora_tests_hooks.py also
   contain tests that interact with an Islandora instance.
"""

import sys
import os
import glob
from ruamel.yaml import YAML
import tempfile
import subprocess
import argparse
import requests
import json
import urllib.parse
import unittest
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workbench_utils
from WorkbenchConfig import WorkbenchConfig


class TestCreate(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'create_test', 'create.yml')
        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]

    def test_create(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 2)

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.create_config_file_path, '--quick_delete_node', 'https://islandora.traefik.me/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        self.rollback_file_path = os.path.join(self.current_dir, 'assets', 'create_test', 'rollback.csv')
        if os.path.exists(self.rollback_file_path):
            os.remove(self.rollback_file_path)

        self.preprocessed_file_path = os.path.join(self.current_dir, 'assets', 'create_test', 'metadata.csv.preprocessed')
        if os.path.exists(self.preprocessed_file_path):
            os.remove(self.preprocessed_file_path)


class TestCreateFromFiles(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'create_from_files_test', 'create.yml')
        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]

    def test_create_from_files(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 3)

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.create_config_file_path, '--quick_delete_node', 'https://islandora.traefik.me/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        self.rollback_file_path = os.path.join(self.current_dir, 'assets', 'create_from_files_test', 'files', 'rollback.csv')
        if os.path.exists(self.rollback_file_path):
            os.remove(self.rollback_file_path)

        if os.path.exists(self.rollback_file_path):
            os.remove(self.rollback_file_path)


class TestCreateWithNewTypedRelation(unittest.TestCase):
    # Note: You can't run this test class on its own, e.g., python3 tests/islandora_tests.py TestCreateWithNewTypedRelation
    # because passing "TestCreateWithNewTypedRelation" as an argument will cause the argparse parser to fail.

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path = os.path.join(self.current_dir, 'assets', 'typed_relation_test', 'create_with_new_typed_relation.yml')
        self.create_cmd = ["./workbench", "--config", self.config_file_path]

        self.temp_dir = tempfile.gettempdir()

        parser = argparse.ArgumentParser()
        parser.add_argument('--config')
        parser.add_argument('--check')
        parser.add_argument('--get_csv_template')
        parser.set_defaults(config=self.config_file_path, check=False)
        args = parser.parse_args()
        workbench_config = WorkbenchConfig(args)
        config = workbench_config.get_config()
        self.config = config

    def test_create_with_new_typed_relation(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 1)

        self.term_id = workbench_utils.find_term_in_vocab(self.config, 'person', 'Kirk, James T.')
        self.assertTrue(self.term_id)

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.config_file_path, '--quick_delete_node', self.config['host'] + '/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        preprocessed_csv_path = os.path.join(self.temp_dir, 'create_with_new_typed_relation.csv.preprocessed')
        if os.path.exists(preprocessed_csv_path):
            os.remove(preprocessed_csv_path)

        term_endpoint = self.config['host'] + '/taxonomy/term/' + str(self.term_id) + '?_format=json'
        delete_term_response = workbench_utils.issue_request(self.config, 'DELETE', term_endpoint)


class TestDelete(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        create_config_file_path = os.path.join(self.current_dir, 'assets', 'delete_test', 'create.yml')
        self.create_cmd = ["./workbench", "--config", create_config_file_path]

        self.temp_dir = tempfile.gettempdir()
        self.nid_file = os.path.join(self.temp_dir, 'workbenchdeletetesttnids.txt')

        nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()
        with open(self.nid_file, "a") as fh:
            fh.write("node_id\n")
            for line in create_lines:
                if 'created at' in line:
                    nid = line.rsplit('/', 1)[-1]
                    nid = nid.strip('.')
                    nids.append(nid)
                    fh.write(nid + "\n")

    def test_delete(self):
        delete_config_file_path = os.path.join(self.current_dir, 'assets', 'delete_test', 'delete.yml')
        delete_cmd = ["./workbench", "--config", delete_config_file_path]
        delete_output = subprocess.check_output(delete_cmd)
        delete_output = delete_output.decode().strip()
        delete_lines = delete_output.splitlines()

        self.assertEqual(len(delete_lines), 5)

    def tearDown(self):
        if os.path.exists(self.nid_file):
            os.remove(self.nid_file)
        if os.path.exists(self.nid_file + ".preprocessed"):
            os.remove(self.nid_file + ".preprocessed")


class TestUpdate(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'update_test', 'create.yml')
        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]

        self.temp_dir = tempfile.gettempdir()
        self.nid_file = os.path.join(self.temp_dir, 'workbenchupdatetestnids.txt')
        self.update_metadata_file = os.path.join(self.current_dir, 'assets', 'update_test', 'workbenchupdatetest.csv')

        yaml = YAML()
        with open(self.create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        config = {}
        for k, v in config_data.items():
            config[k] = v
        self.islandora_host = config['host']

        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()

        with open(self.nid_file, "a") as nids_fh:
            nids_fh.write("node_id\n")
            for line in create_lines:
                if 'created at' in line:
                    nid = line.rsplit('/', 1)[-1]
                    nid = nid.strip('.')
                    nids_fh.write(nid + "\n")
                    self.nids.append(nid)

        # Add some values to the update CSV file to test against.
        with open(self.update_metadata_file, "a") as update_fh:
            update_fh.write("node_id,field_identifier,field_coordinates\n")
            update_fh.write(f'{self.nids[0]},identifier-0001,"99.1,-123.2"')

    def test_update(self):
        # Run update task.
        time.sleep(5)
        update_config_file_path = os.path.join(self.current_dir, 'assets', 'update_test', 'update.yml')
        self.update_cmd = ["./workbench", "--config", update_config_file_path]
        subprocess.check_output(self.update_cmd)

        # Confirm that fields have been updated.
        url = self.islandora_host + '/node/' + str(self.nids[0]) + '?_format=json'
        response = requests.get(url)
        node = json.loads(response.text)
        identifier = str(node['field_identifier'][0]['value'])
        self.assertEqual(identifier, 'identifier-0001')
        coodinates = str(node['field_coordinates'][0]['lat'])
        self.assertEqual(coodinates, '99.1')

    def tearDown(self):
        delete_config_file_path = os.path.join(self.current_dir, 'assets', 'update_test', 'delete.yml')
        delete_cmd = ["./workbench", "--config", delete_config_file_path]
        subprocess.check_output(delete_cmd)

        os.remove(self.nid_file)
        os.remove(self.update_metadata_file)
        nid_file_preprocessed_file = os.path.join(self.temp_dir, 'workbenchupdatetestnids.txt.preprocessed')
        if os.path.exists(nid_file_preprocessed_file):
            os.remove(nid_file_preprocessed_file)
        update_test_csv_preprocessed_file = os.path.join(self.temp_dir, 'workbenchupdatetest.csv.preprocessed')
        if os.path.exists(update_test_csv_preprocessed_file):
            os.remove(update_test_csv_preprocessed_file)
        create_csv_preprocessed_file = os.path.join(self.temp_dir, 'create.csv.preprocessed')
        if os.path.exists(create_csv_preprocessed_file):
            os.remove(create_csv_preprocessed_file)


class TestCreateWithNonLatinText(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        create_config_file_path = os.path.join(self.current_dir, 'assets', 'non_latin_text_test', 'create.yml')
        self.create_cmd = ["./workbench", "--config", create_config_file_path]

        yaml = YAML()
        with open(create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        config = {}
        for k, v in config_data.items():
            config[k] = v
        self.islandora_host = config['host']

        self.temp_dir = tempfile.gettempdir()
        self.nid_file = os.path.join(self.temp_dir, 'workbenchcreatenonlatintestnids.txt')
        self.rollback_file_path = os.path.join(self.current_dir, 'assets', 'non_latin_text_test', 'rollback.csv')

    def test_create_with_non_latin_text(self):
        nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()
        create_lines = create_output.splitlines()
        with open(self.nid_file, "a") as fh:
            fh.write("node_id\n")
            for line in create_lines:
                if 'created at' in line:
                    nid = line.rsplit('/', 1)[-1]
                    nid = nid.strip('.')
                    nids.append(nid)
                    fh.write(nid + "\n")

        self.assertEqual(len(nids), 3)

        url = self.islandora_host + '/node/' + str(nids[0]) + '?_format=json'
        response = requests.get(url)
        node = json.loads(response.text)
        title = str(node['title'][0]['value'])
        self.assertEqual(title, '一九二四年六月十二日')

        url = self.islandora_host + '/node/' + str(nids[1]) + '?_format=json'
        response = requests.get(url)
        node = json.loads(response.text)
        title = str(node['title'][0]['value'])
        self.assertEqual(title, 'सरकारी दस्तावेज़')

        url = self.islandora_host + '/node/' + str(nids[2]) + '?_format=json'
        response = requests.get(url)
        node = json.loads(response.text)
        title = str(node['title'][0]['value'])
        self.assertEqual(title, 'ᐊᑕᐅᓯᖅ ᓄᓇ, ᐅᓄᖅᑐᑦ ᓂᐲᑦ')

    def tearDown(self):
        delete_config_file_path = os.path.join(self.current_dir, 'assets', 'non_latin_text_test', 'delete.yml')
        delete_cmd = ["./workbench", "--config", delete_config_file_path]
        delete_output = subprocess.check_output(delete_cmd)
        delete_output = delete_output.decode().strip()
        delete_lines = delete_output.splitlines()
        os.remove(self.nid_file)

        if os.path.exists(self.rollback_file_path):
            os.remove(self.rollback_file_path)

        preprocessed_csv_path = os.path.join(self.current_dir, 'assets', 'non_latin_text_test', 'metadata.csv.preprocessed')
        if os.path.exists(preprocessed_csv_path):
            os.remove(preprocessed_csv_path)

        nid_file_preprocessed_path = self.nid_file + '.preprocessed'
        if os.path.exists(nid_file_preprocessed_path):
            os.remove(nid_file_preprocessed_path)


class TestSecondaryTask(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_test', 'create.yml')

        yaml = YAML()
        with open(self.create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        config = {}
        for k, v in config_data.items():
            config[k] = v
        self.islandora_host = config['host']

        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]
        self.temp_dir = tempfile.gettempdir()

    def test_secondary_task(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()

        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 5)

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            # Get the node ID of the parent node.
            if node_json['title'][0]['value'].startswith('Tester'):
                parent_nid = node_json['nid'][0]['value']
                break

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            if node_json['title'][0]['value'].startswith('Secondary task test child 1'):
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))
            elif node_json['title'][0]['value'].startswith('Secondary task test child 2'):
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))
            else:
                self.assertEqual(node_json['field_member_of'], [])

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.create_config_file_path, '--quick_delete_node', self.islandora_host + '/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        preprocessed_csv_path = os.path.join(self.current_dir, 'assets', 'secondary_task_test', 'metadata.csv.preprocessed')
        if os.path.exists(preprocessed_csv_path):
            os.remove(preprocessed_csv_path)

        secondary_preprocessed_csv_path = os.path.join(self.temp_dir, 'secondary.csv.preprocessed')
        if os.path.exists(secondary_preprocessed_csv_path):
            os.remove(secondary_preprocessed_csv_path)

        map_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_test', 'id_to_node_map.tsv')
        if os.path.exists(map_file_path):
            os.remove(map_file_path)

        rollback_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_test', 'rollback.csv')
        if os.path.exists(rollback_file_path):
            os.remove(rollback_file_path)


class TestSecondaryTaskWithGoogleSheets(unittest.TestCase):
    """Note: This test fetches data from https://docs.google.com/spreadsheets/d/19AxFWEFuwEoNqH8ciUo0PRAroIpNE9BuBhE5tIE6INQ/edit#gid=0
    """

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_with_google_sheets_and_excel_test', 'google_sheets_primary.yml')

        yaml = YAML()
        with open(self.create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        config = {}
        for k, v in config_data.items():
            config[k] = v
        self.islandora_host = config['host']

        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]
        self.temp_dir = tempfile.gettempdir()

    def test_secondary_task_with_google_sheet(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()

        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 8)

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            # Get the node ID of the parent node.
            if node_json['field_local_identifier'][0]['value'] == 'GSP-04':
                parent_nid = node_json['nid'][0]['value']
                break

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            if node_json['field_local_identifier'][0]['value'] == 'GSC-03':
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))
            if node_json['field_local_identifier'][0]['value'] == 'GSC-04':
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.create_config_file_path, '--quick_delete_node', self.islandora_host + '/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        rollback_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_with_google_sheets_and_excel_test', 'rollback.csv')
        if os.path.exists(rollback_file_path):
            os.remove(rollback_file_path)
        google_sheet_csv_path = os.path.join(self.temp_dir, 'google_sheet.csv')
        if os.path.exists(google_sheet_csv_path):
            os.remove(google_sheet_csv_path)

        secondary_task_google_sheets_csv_paths = glob.glob('*secondary_task_with_google_sheets_and_excel_test_google_sheets_secondary*', root_dir=self.temp_dir)
        for secondary_csv_file_path in secondary_task_google_sheets_csv_paths:
            if os.path.exists(os.path.join(self.temp_dir, secondary_csv_file_path)):
                os.remove(os.path.join(self.temp_dir, secondary_csv_file_path))

        google_sheet_csv_preprocessed_path = os.path.join(self.temp_dir, 'google_sheet.csv.preprocessed')
        if os.path.exists(google_sheet_csv_preprocessed_path):
            os.remove(google_sheet_csv_preprocessed_path)


class TestSecondaryTaskWithExcel(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.create_config_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_with_google_sheets_and_excel_test', 'excel_primary.yml')

        yaml = YAML()
        with open(self.create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        config = {}
        for k, v in config_data.items():
            config[k] = v
        self.islandora_host = config['host']

        self.create_cmd = ["./workbench", "--config", self.create_config_file_path]
        self.temp_dir = tempfile.gettempdir()

    def test_secondary_task_with_excel(self):
        self.nids = list()
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()

        # Write a file to the system's temp directory containing the node IDs of the
        # nodes created during this test so they can be deleted in tearDown().
        create_lines = create_output.splitlines()
        for line in create_lines:
            if 'created at' in line:
                nid = line.rsplit('/', 1)[-1]
                nid = nid.strip('.')
                self.nids.append(nid)

        self.assertEqual(len(self.nids), 8)

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            # Get the node ID of the parent node.
            if node_json['field_local_identifier'][0]['value'] == 'STTP-02':
                parent_nid = node_json['nid'][0]['value']
                break

        for nid in self.nids:
            node_url = self.islandora_host + '/node/' + nid + '?_format=json'
            response = requests.get(node_url)
            node_json = json.loads(response.text)
            if node_json['field_local_identifier'][0]['value'] == 'STTC-01':
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))
            if node_json['field_local_identifier'][0]['value'] == 'STTC-02':
                self.assertEqual(int(node_json['field_member_of'][0]['target_id']), int(parent_nid))

    def tearDown(self):
        for nid in self.nids:
            quick_delete_cmd = ["./workbench", "--config", self.create_config_file_path, '--quick_delete_node', self.islandora_host + '/node/' + nid]
            quick_delete_output = subprocess.check_output(quick_delete_cmd)

        rollback_file_path = os.path.join(self.current_dir, 'assets', 'secondary_task_with_google_sheets_and_excel_test', 'rollback.csv')
        if os.path.exists(rollback_file_path):
            os.remove(rollback_file_path)
        excel_csv_path = os.path.join(self.temp_dir, 'excel.csv')
        if os.path.exists(excel_csv_path):
            os.remove(excel_csv_path)

        secondary_task_excel_csv_paths = glob.glob('*secondary_task_with_google_sheets_and_excel_test_excel_secondary*', root_dir=self.temp_dir)
        for secondary_csv_file_path in secondary_task_excel_csv_paths:
            if os.path.exists(os.path.join(self.temp_dir, secondary_csv_file_path)):
                os.remove(os.path.join(self.temp_dir, secondary_csv_file_path))

        excel_csv_preprocessed_path = os.path.join(self.temp_dir, 'excel.csv.preprocessed')
        if os.path.exists(excel_csv_preprocessed_path):
            os.remove(excel_csv_preprocessed_path)


class TestAdditionalFilesCreate(unittest.TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        create_config_file_path = os.path.join(self.current_dir, 'assets', 'additional_files_test', 'create.yml')

        yaml = YAML()
        with open(create_config_file_path, 'r') as f:
            config_file_contents = f.read()
        config_data = yaml.load(config_file_contents)
        self.config = {}
        for k, v in config_data.items():
            self.config[k] = v
        self.islandora_host = self.config['host']
        self.islandora_username = self.config['username']
        self.islandora_password = self.config['password']

        self.create_cmd = ["./workbench", "--config", create_config_file_path]
        create_output = subprocess.check_output(self.create_cmd)
        create_output = create_output.decode().strip()

        self.temp_dir = tempfile.gettempdir()

        self.rollback_file_path = os.path.join(self.current_dir, 'assets', 'additional_files_test', 'rollback.csv')
        with open(self.rollback_file_path, 'r') as rbf:
            rollback_file_contents = rbf.read()

        # There will only be one nid in the rollback.csv file.
        nid = rollback_file_contents.replace('node_id', '')
        self.nid = nid.strip()

        media_list_url = self.islandora_host + '/node/' + self.nid + '/media?_format=json'
        media_list_response = requests.get(media_list_url, auth=(self.islandora_username, self.islandora_password))
        media_list_json = json.loads(media_list_response.text)
        self.media_sizes = dict()
        self.media_use_tids = dict()
        for media in media_list_json:
            self.media_use_tids[media['mid'][0]['value']] = media['field_media_use'][0]['target_id']
            if 'field_file_size' in media:
                self.media_sizes[media['mid'][0]['value']] = media['field_file_size'][0]['value']
            # We don't use the transcript file's size here since it's not available via REST. Instead, since this
            # file will be the only media with 'field_edited_text' (the transcript), we tack its value onto media_sizes
            # for testing below.
            if 'field_edited_text' in media:
                self.media_sizes['transcript'] = media['field_edited_text'][0]['value']

    def test_media_creation(self):
        # This is the original file's size.
        self.assertTrue(217504 in self.media_sizes.values())
        # This is the preservation file's size.
        self.assertTrue(286445 in self.media_sizes.values())
        # This is the transcript.
        self.assertIn('This is a transcript.', self.media_sizes['transcript'])

    def test_media_use_tids(self):
        '''Doesn't associate media use terms to nodes, but at least it confirms that the intended
           media use tids are present in the media created by this test.
        '''
        preservation_media_use_tid = self.get_term_id_from_uri("http://pcdm.org/use#PreservationMasterFile")
        self.assertTrue(preservation_media_use_tid in self.media_use_tids.values())
        transcript_media_use_tid = self.get_term_id_from_uri("http://pcdm.org/use#Transcript")
        self.assertTrue(transcript_media_use_tid in self.media_use_tids.values())

    def tearDown(self):
        delete_config_file_path = os.path.join(self.current_dir, 'assets', 'additional_files_test', 'rollback.yml')
        delete_cmd = ["./workbench", "--config", delete_config_file_path]
        delete_output = subprocess.check_output(delete_cmd)
        delete_output = delete_output.decode().strip()
        delete_lines = delete_output.splitlines()

        if os.path.exists(self.rollback_file_path):
            os.remove(self.rollback_file_path)

        preprocessed_csv_path = os.path.join(self.temp_dir, 'create.csv.preprocessed')
        if os.path.exists(preprocessed_csv_path):
            os.remove(preprocessed_csv_path)

        rollback_csv_path = os.path.join(self.current_dir, 'assets', 'additional_files_test', 'rollback.csv')
        if os.path.exists(rollback_csv_path):
            os.remove(rollback_csv_path)

        preprocessed_rollback_csv_path = os.path.join(self.temp_dir, 'rollback.csv.preprocessed')
        if os.path.exists(preprocessed_rollback_csv_path):
            os.remove(preprocessed_rollback_csv_path)

    def get_term_id_from_uri(self, uri):
        '''We don't use get_term_from_uri() from workbench_utils because it requires a full config object.
        '''
        term_from_authority_link_url = self.islandora_host + '/term_from_uri?_format=json&uri=' + uri.replace('#', '%23')
        response = requests.get(term_from_authority_link_url, auth=(self.islandora_username, self.islandora_password))
        response_body = json.loads(response.text)
        tid = response_body[0]['tid'][0]['value']
        return tid


if __name__ == '__main__':
    unittest.main()
