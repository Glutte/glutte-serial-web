#!/bin/sh

sudo /usr/bin/openocd -f /usr/share/openocd/scripts/board/stm32f4discovery.cfg -c "init" -c "reset" -c "exit"
