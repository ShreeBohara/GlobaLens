import glcore


def test_package_is_wired_into_the_workspace() -> None:
    assert glcore.__name__ == "glcore"
