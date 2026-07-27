from __future__ import annotations

import unittest
from unittest.mock import patch

from simulation.ui_helpers import runtime_server_identity


class RuntimeServerIdentityTests(unittest.TestCase):
    def test_server_mode_uses_short_hostname(self):
        with patch.dict(
            "os.environ",
            {"PYSDM_LAB_SERVER_MODE": "1"},
            clear=True,
        ), patch("simulation.ui_helpers.socket.gethostname", return_value="cloud7.lab"):
            self.assertEqual(runtime_server_identity(), (True, "cloud7"))

    def test_explicit_server_name_overrides_hostname(self):
        with patch.dict(
            "os.environ",
            {
                "PYSDM_LAB_SERVER_MODE": "1",
                "PYSDM_SERVER_NAME": "cloud5",
            },
            clear=True,
        ), patch("simulation.ui_helpers.socket.gethostname", return_value="cloud7"):
            self.assertEqual(runtime_server_identity(), (True, "cloud5"))

    def test_local_mode_is_distinguishable(self):
        with patch.dict("os.environ", {}, clear=True), patch(
            "simulation.ui_helpers.socket.gethostname",
            return_value="research-pc",
        ):
            self.assertEqual(runtime_server_identity(), (False, "research-pc"))


if __name__ == "__main__":
    unittest.main()
