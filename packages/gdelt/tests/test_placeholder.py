import gdelt


def test_package_is_wired_into_the_workspace() -> None:
    assert gdelt.__name__ == "gdelt"
