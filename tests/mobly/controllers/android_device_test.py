# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from builtins import str as new_str

import io
import logging
import mock
import os
import shutil
import sys
import tempfile
import yaml

from future.tests.base import unittest

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib.services import base_service
from mobly.controllers.android_device_lib.services import logcat

from tests.lib import mock_android_device

MOCK_SNIPPET_PACKAGE_NAME = 'com.my.snippet'

# A mock SnippetClient used for testing snippet management logic.
MockSnippetClient = mock.MagicMock()
MockSnippetClient.package = MOCK_SNIPPET_PACKAGE_NAME


class AndroidDeviceTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.controllers.android_device.
    """

    def setUp(self):
        # Set log_path to logging since mobly logger setup is not called.
        if not hasattr(logging, 'log_path'):
            setattr(logging, 'log_path', '/tmp/logs')
        # Creates a temp dir to be used by tests in this test class.
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Removes the temp dir.
        """
        shutil.rmtree(self.tmp_dir)

    # Tests for android_device module functions.
    # These tests use mock AndroidDevice instances.

    @mock.patch.object(
        android_device,
        'get_all_instances',
        new=mock_android_device.get_all_instances)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_pickup_all(self):
        pick_all_token = android_device.ANDROID_DEVICE_PICK_ALL_TOKEN
        actual_ads = android_device.create(pick_all_token)
        for actual, expected in zip(actual_ads,
                                    mock_android_device.get_mock_ads(5)):
            self.assertEqual(actual.serial, expected.serial)

    @mock.patch.object(
        android_device, 'get_instances', new=mock_android_device.get_instances)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_string_list(self):
        string_list = [u'1', '2']
        actual_ads = android_device.create(string_list)
        for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
            self.assertEqual(actual_ad.serial, expected_serial)

    @mock.patch.object(
        android_device,
        'get_instances_with_configs',
        new=mock_android_device.get_instances_with_configs)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_dict_list(self):
        string_list = [{'serial': '1'}, {'serial': '2'}]
        actual_ads = android_device.create(string_list)
        for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
            self.assertEqual(actual_ad.serial, expected_serial)

    @mock.patch.object(
        android_device,
        'get_instances_with_configs',
        new=mock_android_device.get_instances_with_configs)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device, 'list_adb_devices_by_usb_id', return_value=['usb:1'])
    def test_create_with_usb_id(self, mock_list_adb_devices_by_usb_id):
        string_list = [{'serial': '1'}, {'serial': '2'}, {'serial': 'usb:1'}]
        actual_ads = android_device.create(string_list)
        for actual_ad, expected_serial in zip(actual_ads, ['1', '2', 'usb:1']):
            self.assertEqual(actual_ad.serial, expected_serial)

    def test_create_with_empty_config(self):
        expected_msg = android_device.ANDROID_DEVICE_EMPTY_CONFIG_MSG
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            android_device.create([])

    def test_create_with_not_list_config(self):
        expected_msg = android_device.ANDROID_DEVICE_NOT_LIST_CONFIG_MSG
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            android_device.create('HAHA')

    def test_create_with_no_valid_config(self):
        expected_msg = 'No valid config found in: .*'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            android_device.create([1])

    def test_get_devices_success_with_extra_field(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_label = 'selected'
        expected_count = 2
        for ad in ads[:expected_count]:
            ad.label = expected_label
        selected_ads = android_device.get_devices(ads, label=expected_label)
        self.assertEqual(expected_count, len(selected_ads))
        for ad in selected_ads:
            self.assertEqual(ad.label, expected_label)

    def test_get_devices_no_match(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_msg = ('Could not find a target device that matches condition'
                        ": {'label': 'selected'}.")
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            selected_ads = android_device.get_devices(ads, label='selected')

    def test_get_device_success_with_serial(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_serial = '0'
        ad = android_device.get_device(ads, serial=expected_serial)
        self.assertEqual(ad.serial, expected_serial)

    def test_get_device_success_with_serial_and_extra_field(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_serial = '1'
        expected_h_port = 5555
        ads[1].h_port = expected_h_port
        ad = android_device.get_device(
            ads, serial=expected_serial, h_port=expected_h_port)
        self.assertEqual(ad.serial, expected_serial)
        self.assertEqual(ad.h_port, expected_h_port)

    def test_get_device_no_match(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_msg = ('Could not find a target device that matches condition'
                        ": {'serial': 5}.")
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad = android_device.get_device(ads, serial=len(ads))

    def test_get_device_too_many_matches(self):
        ads = mock_android_device.get_mock_ads(5)
        target_serial = ads[1].serial = ads[0].serial
        expected_msg = r"More than one device matched: \['0', '0'\]"
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            android_device.get_device(ads, serial=target_serial)

    def test_start_services_on_ads(self):
        """Makes sure when an AndroidDevice fails to start some services, all
        AndroidDevice objects get cleaned up.
        """
        msg = 'Some error happened.'
        ads = mock_android_device.get_mock_ads(3)
        ads[0].services.register = mock.MagicMock()
        ads[0].services.stop_all = mock.MagicMock()
        ads[1].services.register = mock.MagicMock()
        ads[1].services.stop_all = mock.MagicMock()
        ads[2].services.register = mock.MagicMock(
            side_effect=android_device.Error(msg))
        ads[2].services.stop_all = mock.MagicMock()
        with self.assertRaisesRegex(android_device.Error, msg):
            android_device._start_services_on_ads(ads)
        ads[0].services.stop_all.assert_called_once_with()
        ads[1].services.stop_all.assert_called_once_with()
        ads[2].services.stop_all.assert_called_once_with()

    def test_start_services_on_ads_skip_logcat(self):
        ads = mock_android_device.get_mock_ads(3)
        ads[0].services.logcat.start = mock.MagicMock()
        ads[1].services.logcat.start = mock.MagicMock()
        ads[2].services.logcat.start = mock.MagicMock(
            side_effect=Exception('Should not have called this.'))
        ads[2].skip_logcat = True
        android_device._start_services_on_ads(ads)

    def test_take_bug_reports(self):
        ads = mock_android_device.get_mock_ads(3)
        android_device.take_bug_reports(ads, 'test_something', 'sometime')
        ads[0].take_bug_report.assert_called_once_with(
            test_name='test_something',
            begin_time='sometime',
            destination=None)
        ads[1].take_bug_report.assert_called_once_with(
            test_name='test_something',
            begin_time='sometime',
            destination=None)
        ads[2].take_bug_report.assert_called_once_with(
            test_name='test_something',
            begin_time='sometime',
            destination=None)

    # Tests for android_device.AndroidDevice class.
    # These tests mock out any interaction with the OS and real android device
    # in AndroidDeivce.

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_instantiation(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        self.assertEqual(ad.serial, '1')
        self.assertEqual(ad.model, 'fakemodel')
        expected_lp = os.path.join(logging.log_path,
                                   'AndroidDevice%s' % mock_serial)
        self.assertEqual(ad.log_path, expected_lp)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_build_info(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        ad = android_device.AndroidDevice(serial='1')
        build_info = ad.build_info
        self.assertEqual(build_info['build_id'], 'AB42')
        self.assertEqual(build_info['build_type'], 'userdebug')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_device_info(self, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        device_info = ad.device_info
        self.assertEqual(device_info['serial'], '1')
        self.assertEqual(device_info['model'], 'fakemodel')
        self.assertEqual(device_info['build_info']['build_id'], 'AB42')
        self.assertEqual(device_info['build_info']['build_type'], 'userdebug')
        ad.add_device_info('sim_type', 'Fi')
        ad.add_device_info('build_id', 'CD42')
        device_info = ad.device_info
        self.assertEqual(device_info['user_added_info']['sim_type'], 'Fi')
        self.assertEqual(device_info['user_added_info']['build_id'], 'CD42')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_serial_is_valid(self, MockFastboot, MockAdbProxy):
        """Verifies that the serial is a primitive string type and serializable.
        """
        ad = android_device.AndroidDevice(serial=1)
        # In py2, checks that ad.serial is not the backported py3 str type,
        # which is not dumpable by yaml in py2.
        # In py3, new_str is equivalent to str, so this check is not
        # appropirate in py3.
        if sys.version_info < (3, 0):
            self.assertFalse(isinstance(ad.serial, new_str))
        self.assertTrue(isinstance(ad.serial, str))
        yaml.safe_dump(ad.serial)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report(self, create_dir_mock,
                                           FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report calls the correct adb command
        and writes the bugreport file to the correct path.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report(
            test_name='test_something', begin_time='sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'test_something,sometime,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1', fail_br=True))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_fail(self, create_dir_mock,
                                                FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report writes out the correct message
        when taking bugreport fails.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        expected_msg = '.* Failed to take bugreport.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.take_bug_report(
                test_name='test_something', begin_time='sometime')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.get_current_epoch_time')
    @mock.patch('mobly.logger.epoch_to_log_line_timestamp')
    def test_AndroidDevice_take_bug_report_without_args(
            self, epoch_to_log_line_timestamp_mock,
            get_current_epoch_time_mock, create_dir_mock, FastbootProxy,
            MockAdbProxy):
        get_current_epoch_time_mock.return_value = 1557446629606
        epoch_to_log_line_timestamp_mock.return_value = '05-09 17:03:49.606'
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report()
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        epoch_to_log_line_timestamp_mock.assert_called_once_with(1557446629606)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'bugreport,05-09_17-03-49.606,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.get_current_epoch_time')
    @mock.patch('mobly.logger.epoch_to_log_line_timestamp')
    def test_AndroidDevice_take_bug_report_with_only_test_name(
            self, epoch_to_log_line_timestamp_mock,
            get_current_epoch_time_mock, create_dir_mock, FastbootProxy,
            MockAdbProxy):
        get_current_epoch_time_mock.return_value = 1557446629606
        epoch_to_log_line_timestamp_mock.return_value = '05-09 17:03:49.606'
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report(test_name='test_something')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        epoch_to_log_line_timestamp_mock.assert_called_once_with(1557446629606)
        self.assertEqual(
            output_path,
            os.path.join(expected_path,
                         'test_something,05-09_17-03-49.606,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_with_only_begin_time(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report(begin_time='sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'bugreport,sometime,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_with_positional_args(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report('test_something', 'sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'test_something,sometime,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_with_destination(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        dest = tempfile.gettempdir()
        output_path = ad.take_bug_report(
            test_name="test_something",
            begin_time="sometime",
            destination=dest)
        expected_path = os.path.join(dest)
        create_dir_mock.assert_called_with(expected_path)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'test_something,sometime,1.zip'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(
            '1', fail_br_before_N=True))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_fallback(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report falls back to traditional
        bugreport on builds that do not have bugreportz.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        output_path = ad.take_bug_report(
            test_name='test_something', begin_time='sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)
        self.assertEqual(output_path,
                         os.path.join(expected_path,
                                      'test_something,sometime,1.txt'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path(self, stop_proc_mock,
                                           start_proc_mock, FastbootProxy,
                                           MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        old_path = ad.log_path
        new_log_path = tempfile.mkdtemp()
        ad.log_path = new_log_path
        self.assertTrue(os.path.exists(new_log_path))
        self.assertFalse(os.path.exists(old_path))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_no_log_exists(
            self, stop_proc_mock, start_proc_mock, FastbootProxy,
            MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        old_path = ad.log_path
        new_log_path = tempfile.mkdtemp()
        ad.log_path = new_log_path
        self.assertTrue(os.path.exists(new_log_path))
        self.assertFalse(os.path.exists(old_path))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('127.0.0.1:5557'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('127.0.0.1:5557'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_with_reserved_character_in_serial_log_path(
            self, stop_proc_mock, start_proc_mock, FastbootProxy,
            MockAdbProxy):
        ad = android_device.AndroidDevice(serial='127.0.0.1:5557')
        base_log_path = os.path.basename(ad.log_path)
        self.assertEqual(base_log_path, 'AndroidDevice127.0.0.1-5557')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_with_service(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.services.register('logcat', logcat.Logcat)
        new_log_path = tempfile.mkdtemp()
        expected_msg = '.* Cannot change `log_path` when there is service running.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.log_path = new_log_path

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_with_existing_file(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        new_log_path = tempfile.mkdtemp()
        new_file_path = os.path.join(new_log_path, 'file.txt')
        with io.open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(u'hahah.')
        expected_msg = '.* Logs already exist .*'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.log_path = new_log_path

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_update_serial(self, stop_proc_mock, start_proc_mock,
                                         creat_dir_mock, FastbootProxy,
                                         MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.update_serial('2')
        self.assertEqual(ad.serial, '2')
        self.assertEqual(ad.debug_tag, ad.serial)
        self.assertEqual(ad.adb.serial, ad.serial)
        self.assertEqual(ad.fastboot.serial, ad.serial)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_update_serial_with_service_running(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.services.register('logcat', logcat.Logcat)
        expected_msg = '.* Cannot change device serial number when there is service running.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.update_serial('2')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet(self, MockGetPort, MockSnippetClient,
                                        MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        self.assertTrue(hasattr(ad, 'snippet'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_getattr(self, MockGetPort, MockSnippetClient,
                                   MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        value = {'value': 42}
        actual_value = getattr(ad, 'some_attr', value)
        self.assertEqual(actual_value, value)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
        return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_package(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = ('Snippet package "%s" has already been loaded under '
                        'name "snippet".') % MOCK_SNIPPET_PACKAGE_NAME
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.load_snippet('snippet2', MOCK_SNIPPET_PACKAGE_NAME)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
        return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_snippet_name(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = '.* Attribute "snippet" already exists, please use a different name.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME + 'haha')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_attribute_name(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        expected_msg = ('Attribute "%s" already exists, please use a different'
                        ' name') % 'adb'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.load_snippet('adb', MOCK_SNIPPET_PACKAGE_NAME)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_start_app_fails(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        """Verifies that the correct exception is raised if start app failed.

        It's possible that the `stop_app` call as part of the start app failure
        teardown also fails. So we want the exception from the start app
        failure.
        """
        expected_e = Exception('start failed.')
        MockSnippetClient.start_app_and_connect = mock.Mock(
            side_effect=expected_e)
        MockSnippetClient.stop_app = mock.Mock(
            side_effect=Exception('stop failed.'))
        ad = android_device.AndroidDevice(serial='1')
        try:
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        except Exception as e:
            assertIs(e, expected_e)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_unload_snippet(self, MockGetPort, MockSnippetClient,
                                          MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        ad.unload_snippet('snippet')
        self.assertFalse(hasattr(ad, 'snippet'))
        with self.assertRaisesRegex(
                android_device.SnippetError,
                '<AndroidDevice|1> No snippet registered with name "snippet"'):
            ad.unload_snippet('snippet')
        # Loading the same snippet again should succeed
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        self.assertTrue(hasattr(ad, 'snippet'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_snippet_cleanup(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.services.start_all()
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        ad.unload_snippet('snippet')
        self.assertFalse(hasattr(ad, 'snippet'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_debug_tag(self, MockFastboot, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        self.assertEqual(ad.debug_tag, '1')
        try:
            raise android_device.DeviceError(ad, 'Something')
        except android_device.DeviceError as e:
            self.assertEqual('<AndroidDevice|1> Something', str(e))
        # Verify that debug tag's setter updates the debug prefix correctly.
        ad.debug_tag = 'Mememe'
        try:
            raise android_device.DeviceError(ad, 'Something')
        except android_device.DeviceError as e:
            self.assertEqual('<AndroidDevice|Mememe> Something', str(e))
        # Verify that repr is changed correctly.
        try:
            raise Exception(ad, 'Something')
        except Exception as e:
            self.assertEqual("(<AndroidDevice|Mememe>, 'Something')", str(e))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_handle_usb_disconnect(self, stop_proc_mock,
                                                 start_proc_mock,
                                                 FastbootProxy, MockAdbProxy):
        class MockService(base_service.BaseService):
            def __init__(self, device, configs=None):
                self._alive = False
                self.pause_called = False
                self.resume_called = False

            @property
            def is_alive(self):
                return self._alive

            def start(self, configs=None):
                self._alive = True

            def stop(self):
                self._alive = False

            def pause(self):
                self._alive = False
                self.pause_called = True

            def resume(self):
                self._alive = True
                self.resume_called = True

        ad = android_device.AndroidDevice(serial='1')
        ad.services.start_all()
        ad.services.register('mock_service', MockService)
        with ad.handle_usb_disconnect():
            self.assertFalse(ad.services.is_any_alive)
            self.assertTrue(ad.services.mock_service.pause_called)
            self.assertFalse(ad.services.mock_service.resume_called)
        self.assertTrue(ad.services.is_any_alive)
        self.assertTrue(ad.services.mock_service.resume_called)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_handle_reboot(self, stop_proc_mock, start_proc_mock,
                                         FastbootProxy, MockAdbProxy):
        class MockService(base_service.BaseService):
            def __init__(self, device, configs=None):
                self._alive = False
                self.pause_called = False
                self.resume_called = False

            @property
            def is_alive(self):
                return self._alive

            def start(self, configs=None):
                self._alive = True

            def stop(self):
                self._alive = False

            def pause(self):
                self._alive = False
                self.pause_called = True

            def resume(self):
                self._alive = True
                self.resume_called = True

        ad = android_device.AndroidDevice(serial='1')
        ad.services.start_all()
        ad.services.register('mock_service', MockService)
        with ad.handle_reboot():
            self.assertFalse(ad.services.is_any_alive)
            self.assertFalse(ad.services.mock_service.pause_called)
            self.assertFalse(ad.services.mock_service.resume_called)
        self.assertTrue(ad.services.is_any_alive)
        self.assertFalse(ad.services.mock_service.resume_called)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device.AndroidDevice.is_boot_completed',
        side_effect=[False, False, adb.AdbTimeoutError(
            ['adb', 'shell', 'getprop sys.boot_completed'],
            timeout=5, serial=1), True])
    @mock.patch('time.sleep', return_value=None)
    @mock.patch('time.time', side_effect=[0, 5, 10, 15, 20, 25, 30])
    def test_AndroidDevice_wait_for_completion_completed(
            self, MockTime, MockSleep, MockIsBootCompleted, FastbootProxy,
            MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        raised = False
        try:
            ad.wait_for_boot_completion()
        except (adb.AdbError, adb.AdbTimeoutError):
            raised = True
        self.assertFalse(raised, 'adb.AdbError or adb.AdbTimeoutError exception raised but not handled.')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device.AndroidDevice.is_boot_completed',
        side_effect=[False, False, adb.AdbTimeoutError(
            ['adb', 'shell', 'getprop sys.boot_completed'],
            timeout=5, serial=1), False, False, False, False])
    @mock.patch('time.sleep', return_value=None)
    @mock.patch('time.time', side_effect=[0, 5, 10, 15, 20, 25, 30])
    def test_AndroidDevice_wait_for_completion_never_boot(
            self, MockTime, MockSleep, MockIsBootCompleted, FastbootProxy,
            MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        raised = False
        try:
            with self.assertRaises(android_device.DeviceError):
                ad.wait_for_boot_completion(timeout=20)
        except (adb.AdbError, adb.AdbTimeoutError):
            raised = True
        self.assertFalse(raised, 'adb.AdbError or adb.AdbTimeoutError exception raised but not handled.')


if __name__ == '__main__':
    unittest.main()
