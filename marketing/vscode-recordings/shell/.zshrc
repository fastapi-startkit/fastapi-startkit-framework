PROMPT='%F{green}➜%f  %F{cyan}%1~%f '
PROMPT_EOL_MARK=''
unset VIRTUAL_ENV
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_ADDOPTS="-W ignore::pytest.PytestRemovedIn10Warning -W ignore::pytest.PytestDeprecationWarning"
