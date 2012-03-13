#!/usr/bin/env bash

echo "Bash options:"
set -o errexit

me=$(basename $0)
echo
echo "[$me] $@"
echo

echo "[$me] Initial file listing"
ls

binary=ProtoMol
echo "[$me] Ensuring core is present"
[ ! -f $binary ] &&
wget "http://www.nd.edu/~cabdulwa/$binary"
chmod a+x $binary

echo "[$me] Running simulation"
./with-env ./env.sh ./$binary protomol.conf

mkdir -p output/traj
mv *xtc output/traj
echo "[$me] Assigning trajectory to MSM states"
mkdir Data
cp -v Gens.lh5 Data
./with-env env.sh ConvertDataToHDF.py -s state0.pdb -I output
./with-env env.sh Assign.py
./with-env env.sh ConvertAssignToText.py


echo "[$me] updating cell assignment"
tail -1 Data/discrete.traj > cell2.dat

echo "[$me] checking if result files exist"
ls structure2.pdb cell2.dat

echo "[$me] Compressing results"
resultfile=results.tar
tar cfv $resultfile *.energy* *.pdb *.dat Data/discrete.traj Data/tCounts.UnSym.mtx output/*


echo "[$me] Cleaning up"
rm -rv Data output Trajectories ProjectInfo.h5


echo "[$me] Returning files"
ls $resultfile