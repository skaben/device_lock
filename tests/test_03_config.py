def test_empty_config(get_config, default_config):
    config_dict = default_config("initial")
    config = get_config(config_dict)
    assert config.minimal_essential_conf == config_dict, "minimal essential has changed"


def test_existent_config(get_config, default_config):
    config_dict = default_config("default")
    config = get_config(config_dict)
    assert config.data == config_dict, "config data not loaded"