from app import config, main


def test_main() -> None:
    assert main.main() == config.RETURN_VALUE
