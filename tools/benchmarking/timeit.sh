#!/bin/bash

set -eu

flush () {
    sudo sync; sudo sh -c 'echo 3 >/proc/sys/vm/drop_caches'
}

run_cmd() {
    d="$1"
    shift
    echo "= Command: $@ "
    echo "== Cold $@"
    flush
    /usr/bin/time -f "\t%E real,\t%U user,\t%S sys" "$@"
    if [ -e $d ]; then
        echo "== Warm/repeated"
        /usr/bin/time -f "\t%E real,\t%U user,\t%S sys" "$@"
    fi
}

for d in "$@"; do run_cmd $d du -scm $d; done
echo
echo
for d in "$@"; do run_cmd $d tar -cf $d.tgz $d; done
echo
echo
for d in "$@"; do run_cmd $d chmod +w -R $d/.git/annex/objects; done
echo
echo
for d in "$@"; do run_cmd $d rm -rf $d; done