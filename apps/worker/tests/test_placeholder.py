import worker


def test_package_is_wired_into_the_workspace() -> None:
    assert worker.__name__ == "worker"
