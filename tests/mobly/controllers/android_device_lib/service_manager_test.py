# Copyright 2018 Google Inc.
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
"""Unit tests for Mobly's ServiceManager."""
import mock
import sys

from future.tests.base import unittest

from mobly import expects
from mobly.controllers.android_device_lib import service_manager
from mobly.controllers.android_device_lib.services import base_service


class MockService(base_service.BaseService):
    def __init__(self, device, configs=None):
        self._device = device
        self._configs = configs
        self._alive = False
        self.start_func = mock.MagicMock()
        self.stop_func = mock.MagicMock()
        self.pause_func = mock.MagicMock()
        self.resume_func = mock.MagicMock()

    @property
    def is_alive(self):
        return self._alive

    def start(self, configs=None):
        self.start_func(configs)
        self._alive = True

    def stop(self):
        self.stop_func()
        self._alive = False

    def pause(self):
        self.pause_func()

    def resume(self):
        self.resume_func()


class ServiceManagerTest(unittest.TestCase):
    def setUp(self):
        # Reset hidden global `expects` state.
        if sys.version_info < (3, 0):
            reload(expects)
        else:
            import importlib
            importlib.reload(expects)

    def assert_recorded_one_error(self, message):
        self.assertEqual(expects.recorder.error_count, 1)
        for _, error in (
                expects.DEFAULT_TEST_RESULT_RECORD.extra_errors.items()):
            self.assertIn(message, error.details)

    def test_service_manager_instantiation(self):
        manager = service_manager.ServiceManager(mock.MagicMock())

    def test_register(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService)
        service = manager.mock_service
        self.assertTrue(service)
        self.assertTrue(service.is_alive)
        self.assertTrue(manager.is_any_alive)
        self.assertEqual(service.start_func.call_count, 1)

    def test_register_with_configs(self):
        mock_configs = mock.MagicMock()
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService, configs=mock_configs)
        service = manager.mock_service
        self.assertTrue(service)
        self.assertEqual(service._configs, mock_configs)
        self.assertEqual(service.start_func.call_count, 1)

    def test_register_do_not_start_service(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService, start_service=False)
        service = manager.mock_service
        self.assertTrue(service)
        self.assertFalse(service.is_alive)
        self.assertFalse(manager.is_any_alive)
        self.assertEqual(service.start_func.call_count, 0)

    def test_register_not_a_class(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        with self.assertRaisesRegex(service_manager.Error,
                                    '.* is not a class!'):
            manager.register('mock_service', base_service)

    def test_register_wrong_subclass_type(self):
        class MyClass(object):
            pass

        manager = service_manager.ServiceManager(mock.MagicMock())
        with self.assertRaisesRegex(service_manager.Error,
                                    '.* is not a subclass of BaseService!'):
            manager.register('mock_service', MyClass)

    def test_register_dup_alias(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService)
        msg = '.* A service is already registered with alias "mock_service"'
        with self.assertRaisesRegex(service_manager.Error, msg):
            manager.register('mock_service', MockService)

    def test_unregister(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService)
        service = manager.mock_service
        manager.unregister('mock_service')
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service.is_alive)
        self.assertEqual(service.stop_func.call_count, 1)

    def test_unregister_not_started_service(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService, start_service=False)
        service = manager.mock_service
        manager.unregister('mock_service')
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service.is_alive)
        self.assertEqual(service.stop_func.call_count, 0)

    def test_unregister_non_existent(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        with self.assertRaisesRegex(
                service_manager.Error,
                '.* No service is registered with alias "mock_service"'):
            manager.unregister('mock_service')

    def test_unregister_handle_error_from_stop(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service', MockService)
        service = manager.mock_service
        service.stop_func.side_effect = Exception('Something failed in stop.')
        manager.unregister('mock_service')
        self.assert_recorded_one_error(
            'Failed to stop service instance "mock_service".')

    def test_unregister_all(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.unregister_all()
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)
        self.assertEqual(service1.stop_func.call_count, 1)
        self.assertEqual(service2.stop_func.call_count, 1)

    def test_unregister_all_with_some_failed(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1.stop_func.side_effect = Exception('Something failed in stop.')
        service2 = manager.mock_service2
        manager.unregister_all()
        self.assertFalse(manager.is_any_alive)
        self.assertTrue(service1.is_alive)
        self.assertFalse(service2.is_alive)
        self.assert_recorded_one_error(
            'Failed to stop service instance "mock_service1".')

    def test_start_all(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService, start_service=False)
        manager.register('mock_service2', MockService, start_service=False)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.start_all()
        self.assertTrue(service1.is_alive)
        self.assertTrue(service2.is_alive)
        self.assertEqual(service1.start_func.call_count, 1)
        self.assertEqual(service2.start_func.call_count, 1)

    def test_start_all_with_already_started_services(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService, start_service=False)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.start_all()
        manager.start_all()
        self.assertTrue(service1.is_alive)
        self.assertTrue(service2.is_alive)
        self.assertEqual(service1.start_func.call_count, 1)
        self.assertEqual(service2.start_func.call_count, 1)

    def test_start_all_with_some_failed(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService, start_service=False)
        manager.register('mock_service2', MockService, start_service=False)
        service1 = manager.mock_service1
        service1.start_func.side_effect = Exception(
            'Something failed in start.')
        service2 = manager.mock_service2
        manager.start_all()
        self.assertFalse(service1.is_alive)
        self.assertTrue(service2.is_alive)
        self.assert_recorded_one_error(
            'Failed to start service "mock_service1"')

    def test_stop_all(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.stop_all()
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)
        self.assertEqual(service1.start_func.call_count, 1)
        self.assertEqual(service2.start_func.call_count, 1)
        self.assertEqual(service1.stop_func.call_count, 1)
        self.assertEqual(service2.stop_func.call_count, 1)

    def test_stop_all_with_already_stopped_services(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService, start_service=False)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.stop_all()
        manager.stop_all()
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)
        self.assertEqual(service1.start_func.call_count, 1)
        self.assertEqual(service2.start_func.call_count, 0)
        self.assertEqual(service1.stop_func.call_count, 1)
        self.assertEqual(service2.stop_func.call_count, 0)

    def test_stop_all_with_some_failed(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1.stop_func.side_effect = Exception(
            'Something failed in start.')
        service2 = manager.mock_service2
        manager.stop_all()
        self.assertTrue(service1.is_alive)
        self.assertFalse(service2.is_alive)
        self.assert_recorded_one_error(
            'Failed to stop service "mock_service1"')

    def test_start_all_and_stop_all_serveral_times(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService, start_service=False)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.stop_all()
        manager.start_all()
        manager.stop_all()
        manager.start_all()
        manager.stop_all()
        manager.start_all()
        self.assertTrue(service1.is_alive)
        self.assertTrue(service2.is_alive)
        self.assertEqual(service1.start_func.call_count, 4)
        self.assertEqual(service2.start_func.call_count, 3)
        self.assertEqual(service1.stop_func.call_count, 3)
        self.assertEqual(service2.stop_func.call_count, 2)

    def test_pause_all(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.pause_all()
        self.assertEqual(service1.pause_func.call_count, 1)
        self.assertEqual(service2.pause_func.call_count, 1)
        self.assertEqual(service1.resume_func.call_count, 0)
        self.assertEqual(service2.resume_func.call_count, 0)

    def test_pause_all_with_some_failed(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1.pause_func.side_effect = Exception(
            'Something failed in pause.')
        service2 = manager.mock_service2
        manager.pause_all()
        self.assertEqual(service1.pause_func.call_count, 1)
        self.assertEqual(service2.pause_func.call_count, 1)
        self.assertEqual(service1.resume_func.call_count, 0)
        self.assertEqual(service2.resume_func.call_count, 0)
        self.assert_recorded_one_error(
            'Failed to pause service "mock_service1".')

    def test_resume_all(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.pause_all()
        manager.resume_all()
        self.assertEqual(service1.pause_func.call_count, 1)
        self.assertEqual(service2.pause_func.call_count, 1)
        self.assertEqual(service1.resume_func.call_count, 1)
        self.assertEqual(service2.resume_func.call_count, 1)

    def test_resume_all_with_some_failed(self):
        manager = service_manager.ServiceManager(mock.MagicMock())
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1.resume_func.side_effect = Exception(
            'Something failed in resume.')
        service2 = manager.mock_service2
        manager.pause_all()
        manager.resume_all()
        self.assertEqual(service1.pause_func.call_count, 1)
        self.assertEqual(service2.pause_func.call_count, 1)
        self.assertEqual(service1.resume_func.call_count, 1)
        self.assertEqual(service2.resume_func.call_count, 1)
        self.assert_recorded_one_error(
            'Failed to resume service "mock_service1".')


if __name__ == '__main__':
    unittest.main()
