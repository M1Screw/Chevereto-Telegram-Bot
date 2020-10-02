#!/bin/bash
cd `dirname $0`
eval $(ps -ef | grep "[0-9] python3 bot\\.py m" | awk '{print "kill "$2}')
ulimit -n 512000
nohup python3 bot.py m>> bot.log 2>&1 &