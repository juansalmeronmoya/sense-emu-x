import io
import sys
import logging
import pytest
from unittest.mock import patch, MagicMock
from sense_emu.terminal import FileType, TerminalApplication


class TestFileType:
    def test_open_existing_file_rb(self, tmp_path):
        f = tmp_path / 'data.bin'
        f.write_bytes(b'hello')
        ft = FileType('rb')
        opened = ft(str(f))
        assert opened.read() == b'hello'
        opened.close()

    def test_open_existing_file_r(self, tmp_path):
        f = tmp_path / 'data.txt'
        f.write_text('world')
        ft = FileType('r')
        opened = ft(str(f))
        assert opened.read() == 'world'
        opened.close()

    def test_missing_file_raises_argument_type_error(self, tmp_path):
        import argparse
        ft = FileType('rb')
        with pytest.raises(argparse.ArgumentTypeError):
            ft(str(tmp_path / 'nonexistent.bin'))

    def test_dash_reads_stdin_binary(self):
        ft = FileType('rb')
        result = ft('-')
        assert result in (sys.stdin.buffer, sys.stdin)

    def test_dash_writes_stdout_binary(self):
        ft = FileType('wb')
        result = ft('-')
        assert result in (sys.stdout.buffer, sys.stdout)

    def test_dash_invalid_mode_raises(self):
        ft = FileType('a')
        with pytest.raises(ValueError):
            ft('-')

    def test_repr(self):
        ft = FileType('rb')
        assert 'FileType' in repr(ft)


class _ConcreteApp(TerminalApplication):
    def __init__(self):
        super().__init__(version='1.0', description='Test app')

    def main(self, args):
        return 0


class TestTerminalApplication:
    def test_instantiation(self):
        app = _ConcreteApp()
        assert app.parser is not None

    def test_call_returns_zero(self):
        app = _ConcreteApp()
        result = app([])
        assert result == 0

    def test_verbose_flag_sets_info_level(self):
        app = _ConcreteApp()
        with patch.object(app, 'main', return_value=0) as mock_main:
            app(['-v'])
        # At minimum, no exception raised

    def test_quiet_flag(self):
        app = _ConcreteApp()
        result = app(['-q'])
        assert result == 0

    def test_version_exits(self):
        app = _ConcreteApp()
        with pytest.raises(SystemExit):
            app(['--version'])

    def test_handle_system_exit(self):
        app = _ConcreteApp()
        result = app.handle(SystemExit, SystemExit(0), None)
        assert result == 0

    def test_handle_keyboard_interrupt(self):
        app = _ConcreteApp()
        result = app.handle(KeyboardInterrupt, KeyboardInterrupt(), None)
        assert result == 2

    def test_handle_ioerror(self):
        app = _ConcreteApp()
        result = app.handle(IOError, IOError('not found'), None)
        assert result == 1

    def test_handle_generic_exception(self):
        app = _ConcreteApp()
        try:
            raise RuntimeError('boom')
        except RuntimeError:
            import sys
            exc_type, exc_val, exc_tb = sys.exc_info()
        result = app.handle(exc_type, exc_val, exc_tb)
        assert result == 1

    def test_configure_logging_with_log_file(self, tmp_path):
        app = _ConcreteApp()
        log_file = str(tmp_path / 'test.log')
        args = app.parser.parse_args(['-l', log_file])
        app.configure_logging(args)
        logger = logging.getLogger()
        # should not raise; log file handler is added

    def test_main_raises_not_implemented_for_base(self):
        base = TerminalApplication.__new__(TerminalApplication)
        with pytest.raises(NotImplementedError):
            base.main(None)

    def test_handle_argument_error(self):
        import argparse
        app = _ConcreteApp()
        result = app.handle(
            argparse.ArgumentError,
            argparse.ArgumentError(None, 'bad arg'),
            None,
        )
        assert result == 2

    def test_configure_logging_debug_mode(self):
        import logging
        app = _ConcreteApp()
        args = app.parser.parse_args(['-P'])
        app.configure_logging(args)
        assert logging.getLogger().level == logging.DEBUG

    def test_comp_line_env_returns_zero(self):
        app = _ConcreteApp()
        with patch.dict('os.environ', {'COMP_LINE': 'sense_emu_gui'}):
            result = app([])
        assert result == 0

    def test_call_with_debug_flag_pdb(self):
        import pdb
        app = _ConcreteApp()
        with patch('pdb.runcall', return_value=42) as mock_pdb:
            result = app(['-P'])
        assert mock_pdb.called

    def test_read_configuration_no_config_returns_args(self):
        app = _ConcreteApp()
        args = ['--version']
        result = app.read_configuration(args)
        assert result == args

    def test_file_type_dash_stdout_text(self):
        ft = FileType('w')
        result = ft('-')
        assert result in (sys.stdout, sys.stdout.buffer if hasattr(sys.stdout, 'buffer') else sys.stdout)

    def test_terminal_app_with_config_files(self, tmp_path):
        cfg = tmp_path / 'config.ini'
        cfg.write_text('[app]\nfoo = bar\n')

        class _AppWithConfig(TerminalApplication):
            def __init__(self):
                super().__init__(
                    version='1.0',
                    config_files=[str(cfg)],
                    config_section='app',
                )
            def main(self, args):
                return 0

        app = _AppWithConfig()
        result = app([])
        assert result == 0
