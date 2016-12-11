#!/usr/bin/env bash

if [[ "$TRAVIS_OS_NAME" == "osx" ]]; then
  brew update
  brew outdated pyenv || brew upgrade pyenv
  eval "$(pyenv init -)"
  pyenv install $PYTHON_VERSION
  pyenv local $PYTHON_VERSION
fi
