#!/bin/bash
sleep 5
amixer -c 2 sset Mic capture 7% 2>/dev/null
amixer -c 2 sset Speaker 0% mute 2>/dev/null
sleep 5
amixer -c 2 sset Mic capture 7% 2>/dev/null
amixer -c 2 sset Speaker 0% mute 2>/dev/null
