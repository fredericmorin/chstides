#!/usr/bin/env bash
set -e

DEVCONFIG=".devconfig"

mkdir -p "$DEVCONFIG/custom_components"

if [ ! -L "$DEVCONFIG/custom_components/chstides" ]; then
    ln -s "$(pwd)/custom_components/chstides" "$DEVCONFIG/custom_components/chstides"
fi

pip install homeassistant --quiet
hass -c "$DEVCONFIG"
