from whatsapp_capitalize import settings


def test_settings_round_trip_and_ignore_unknown_values(tmp_path):
    path = tmp_path / "settings.json"
    settings.save(path, {"capitalize": False, "fix_words": True, "unknown": False})

    assert settings.load(path) == {"capitalize": False, "fix_words": True}


def test_invalid_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")

    assert settings.load(path) == settings.DEFAULTS
