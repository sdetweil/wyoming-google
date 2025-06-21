#!/bin/bash
server=localhost
if [ $# -gt 0 ]; then 
  server=$1
fi  
test/wav2text.sh tcp://${server}:10555 test.wav test1.wav --language en 
