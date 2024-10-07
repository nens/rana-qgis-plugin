#!/bin/bash
set -e
set -u

VERSION=$(grep "^version" ./rana_qgis_plugin/metadata.txt | cut -d= -f2)

# ARTIFACTS_KEY is set as env variable in the github action.
# For now you have to set it manually locally.
ARTIFACT=rana_qgis_plugin.${VERSION}.zip
PROJECT=rana-qgis-plugin

curl -X POST \
     --retry 3 \
     -H "Content-Type: multipart/form-data" \
     -F key=${ARTIFACTS_KEY} \
     -F artifact=@${ARTIFACT} \
     https://artifacts.lizard.net/upload/${PROJECT}/
