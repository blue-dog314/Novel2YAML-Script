"""Import smoke test for the exporters placeholder package."""

import exporters


def test_module_name() -> None:
    assert exporters.MODULE_NAME == "exporters"
