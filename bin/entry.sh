#!/bin/bash

/home/hummingbot/miniconda3/envs/$(head -1 setup/environment-linux.yml | cut -d' ' -f2)/bin/python3 \
	bin/hummingbot_quickstart.py --auto-set-permissions $(id -nu):$(id -ng)
