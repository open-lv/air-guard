#!/bin/bash
set -e
echo "Collecting build into \"$(pwd)/build\""

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
MICROPYTHON_SOFTWARE_DIR="${SCRIPT_DIR}"/../../firmware/micropython

# Collect build
[ ! -d "build" ] && mkdir build
# -f to ignore empty build dir
rm -rf build/*
mkdir -p build/original
cp "${MICROPYTHON_SOFTWARE_DIR}"/*.py build/
cp "${MICROPYTHON_SOFTWARE_DIR}"/original/*.py build/original/

cp -r "${MICROPYTHON_SOFTWARE_DIR}"/original/assets/ build/original/assets/

cp -r "${MICROPYTHON_SOFTWARE_DIR}"/original/static/ build/original/static/

rm -r build/original/static/mock/
sed -i'' -e "s:const mock = true;:const mock = false;:g" build/original/static/sargsAPI.js
gzip -r build/original/static/*

# create a version file
AIRGUARD_VERSION=`git describe`
echo "VERSION='$AIRGUARD_VERSION'" > build/airguardversion.py

echo "Build collection finished"
set +e