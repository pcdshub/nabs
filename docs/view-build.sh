#!/bin/bash
firefox --no-remote "file://$(readlink -f ./build/html/index.html)"
