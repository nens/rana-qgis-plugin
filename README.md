# rana-qgis-plugin

A QGIS Rana plugin for exploring files in the Rana project.

Local development notes
-----------------------

On Linux, local development happens with docker to make sure we're working in a nicely
isolated environment. To start the development environment, run the following commands::

    $ docker compose build
    $ xhost +local:docker
    $ docker compose up

## Releasing

First make sure the version in the metadata is set correctly.

    $ python3 zip_plugin.py
    $ ARTIFACTS_KEY=abcdefg ./upload-artifact.sh

The `ARTIFACTS_KEY` environment variable is something you have to set manually
(i.e. Reinout probably mailed it to you). Later on we can set up an automatic
github action if needed.

It uploads to https://plugins.lizard.net (which is the same as
https://plugins.3di.live ).
