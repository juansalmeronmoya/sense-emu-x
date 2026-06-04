import re

with open("setup.cfg", "r") as f:
    content = f.read()

# Add entry points
entry_points_patch = """
[options.entry_points]
console_scripts =
    sense_rec = sense_emu.record:app
    sense_play = sense_emu.play:app
    sense_csv = sense_emu.dump:app
    sense_emu_tui = sense_emu.tui:main
gui_scripts =
    sense_emu_gui = sense_emu.gui:main
    sense_emu_pyside = sense_emu.pyside_app:main
"""
content = re.sub(r"\[options\.entry_points\].*?(?=\n\[|$)", entry_points_patch.strip(), content, flags=re.DOTALL)

extras_patch = """
[options.extras_require]
test =
    pytest
    pytest-cov
    mock
doc =
    sphinx
    sphinx-rtd-theme
tui =
    textual
pyside =
    PySide6
"""
content = re.sub(r"\[options\.extras_require\].*?(?=\n\[options\.entry_points\]|$)", extras_patch.strip() + "\n\n", content, flags=re.DOTALL)

with open("setup.cfg", "w") as f:
    f.write(content)
