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

import unittest
import pytz

from mobly import logger


class LoggerTest(unittest.TestCase):
    """Verifies code in mobly.logger module.
    """

    def test_epoch_to_log_line_timestamp(self):
        actual_stamp = logger.epoch_to_log_line_timestamp(
            1469134262116, time_zone=pytz.utc)
        self.assertEqual("07-21 20:51:02.116", actual_stamp)

    def test_is_valid_logline_timestamp(self):
        self.assertTrue(
            logger.is_valid_logline_timestamp("06-21 17:44:42.336"))

    def test_is_valid_logline_timestamp_when_wrong_length(self):
        self.assertFalse(
            logger.is_valid_logline_timestamp("  06-21 17:44:42.336"))

    def test_is_valid_logline_timestamp_when_invalid_content(self):
        self.assertFalse(
            logger.is_valid_logline_timestamp("------------------"))


if __name__ == "__main__":
    unittest.main()
