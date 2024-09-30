# rana-qgis-plugin

A QGIS Rana plugin for exploring files and folders in the Rana project.

Local development notes
-----------------------

On Linux, local development happens with docker to make sure we're working in a nicely
isolated environment. To start the development environment, run the following commands::

    $ docker compose build
    $ xhost +local:docker
    $ docker compose up
