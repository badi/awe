#!/usr/bin/env bash

set -o errexit

#################################################################################
#############################  setting up the test  #############################

### be able to use modules in bash
# source /afs/crc.nd.edu/x86_64_linux/Modules/current/init/bash

### load external dependencies
module purge
module use /afs/crc.nd.edu/user/c/cabdulwa/Public/modulefiles

# build dependencies
module load xdrfile gsl 

# runtime dependencies
module load python/2.7.1 numpy/1.5.1 prody/0.9.4 gromacs/4.5.5 matplotlib
module load /afs/nd.edu/user37/ccl/software/modulefiles/cctools/autobuild


### need a sandbox to work in
workarea=$(mktemp -d /tmp/awe-dev-test.XXX)
pref=$workarea/awe-install
pyp=$pref/lib/python2.7/site-packages

### processes to kill on cleanup
KILL_PIDS=

cleanup() {
	rm -rf $workarea
	for p in $KILL_PIDS; do
		kill -9 $p
	done
}

mark-cleanup-pid() {
	local p=$1
	KILL_PIDS="$KILL_PIDS $p"
}

trap cleanup EXIT


#################################################################################
############################# actually run the test #############################

### install
./configure --prefix $pref
make install

### setup environment
export PATH=$pref/bin:$PATH
export PYTHONPATH=$pyp:$PYTHONPATH

### go to sandbox
pushd $workarea
mkdir ala-example
cd ala-example

### run awe
awe-prepare
python awe-ala.py -r 0 -i 5 -d all &
pid=$!
mark-cleanup-pid $pid

### start some workers
for i in `seq 20`; do
	work_queue_worker localhost 9123 &
	mark-cleanup-pid $!
done

wait $pid

### generate the ramachandran plot
awe-rama-ala.py \
	-w cell-weights.csv \
	-p awe-instance-data/topol.pdb \
	-c awe-instance-data/cells.dat \
	-n 100

test -f awe-rama-ala.png

### visualize forward and backward fluxes
awe-flux.py -i color-transition-matrix.csv -l 0.01

fluxoutputs=(
	instan-forward-flux.dat
	instan-backward-flux.dat
	forward-flux.png
	backward-flux.png
)

for p in ${fluxoutputs[@]}; do
	test -f $p
done

### generate transition probability matrix
awe-transMatrix.py -p walker-history.csv -w walker-weights.csv -t 1 -n 100

test -f trans-probability-matrix.csv
