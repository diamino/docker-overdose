#!/bin/sh

TEST_USER='testuser'
TEST_HOST='10.0.0.1'
SNIFF_CONTAINER='network-test'

if [[ $OSTYPE == "darwin"* ]]; then
    alias wireshark='/Applications/Wireshark.app/Contents/MacOS/Wireshark'
fi

ssh $TEST_USER@$TEST_HOST "docker run --rm -i -a stdout --net=container:$1 --cap-add=NET_ADMIN $SNIFF_CONTAINER tcpdump -s 0 -U -n -w - -i eth0" | wireshark -k -i - 
