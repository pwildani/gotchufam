#!/bin/bash

if [ x"$1" == xPROD ]; then
  CODE_ROOT=/home/protected/gotchufam
else
  CODE_ROOT=./release
fi

mkdir $CODE_ROOT
cd $CODE_ROOT
python -m virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp -rv "$(dirname "$0")"/. "$CODE_ROOT"
