"""Import smoke test for the generation placeholder package."""

import generation


def test_module_name() -> None:
    assert generation.MODULE_NAME == "generation"
