#!/usr/bin/env bash

set -o errexit

gendir=$1
run=$2
clone=$3
gen=$4

me=$(basename $0)

echo "[$me] $gendir $run $clone $gen"

cd $gendir

ran=$RANDOM
echo "[$0] setting new seed: $ran"
sed -i "s:^seed *[0-9]*:seed $ran:" protomol.conf

echo "[$0] backing up MD logfile"
if [ -f my_md_logfile.txt ]; then
    mv -v --backup=numbered my_md_logfile.txt{,.bkp}
fi

echo "[$0] removing ala2.pdb if it exists"
if [ -f ala2.pdb ]; then
    rm -v ala2.pdb
fi
