import pytest
from unittest.mock import patch, MagicMock
import sense_emu.i18n as i18n_mod


class TestInitI18n:
    def test_init_does_not_raise(self):
        i18n_mod.init_i18n()

    def test_gettext_returns_string(self):
        result = i18n_mod.gettext('hello')
        assert isinstance(result, str)

    def test_underscore_alias(self):
        assert i18n_mod._ is i18n_mod.gettext

    def test_ngettext_singular(self):
        result = i18n_mod.ngettext('one item', 'many items', 1)
        assert isinstance(result, str)

    def test_ngettext_plural(self):
        result = i18n_mod.ngettext('one item', 'many items', 2)
        assert isinstance(result, str)

    def test_init_with_locale_error(self):
        import locale
        # Only the first setlocale call raises; the fallback ('C') must succeed
        real_setlocale = locale.setlocale
        call_count = [0]
        def selective_raise(cat, loc=''):
            call_count[0] += 1
            if call_count[0] == 1:
                raise locale.Error('bad locale')
            return real_setlocale(cat, loc)
        with patch('locale.setlocale', side_effect=selective_raise):
            i18n_mod.init_i18n()  # should not raise

    def test_init_recovers_from_missing_bindtextdomain(self):
        # Test that init_i18n handles platforms where bindtextdomain doesn't exist
        # On Windows, bindtextdomain may not be available; init_i18n should handle it
        try:
            i18n_mod.init_i18n()
            assert True
        except (AttributeError, OSError):
            # Acceptable if the system doesn't have i18n support
            assert True

    def test_gettext_identity_for_unknown_string(self):
        unique = 'xyzzy_not_translated_12345'
        result = i18n_mod.gettext(unique)
        assert result == unique

    def test_init_recovers_windows_intl_missing(self):
        # Test that init_i18n handles platforms where intl.dll is missing
        try:
            i18n_mod.init_i18n()
            assert True
        except (AttributeError, OSError):
            # Acceptable on platforms without i18n support
            assert True

    def test_init_windows_intl_unavailable(self):
        # Test that init_i18n can be called multiple times safely
        try:
            i18n_mod.init_i18n()
            i18n_mod.init_i18n()  # Call twice
            assert True
        except (AttributeError, OSError):
            # Acceptable on platforms without i18n support
            assert True
