PROMPT='%F{green}➜%f  %F{cyan}startkit-demo%f '
unset VIRTUAL_ENV
export PYTEST_ADDOPTS="-W ignore::pytest.PytestRemovedIn10Warning -W ignore::pytest.PytestDeprecationWarning"
PROMPT_EOL_MARK=''
export PYTHONDONTWRITEBYTECODE=1
