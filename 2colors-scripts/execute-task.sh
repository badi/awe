#!/usr/bin/env bash

echo "Bash options:"
set -o

me=$(basename $0)
echo
echo "[$me] $@"
echo

run=$1;shift
clone=$1;shift
gen=$1;shift

requiredFiles="$@"

workarea=RUN$run-CLONE$clone-GEN$gen

[ -d $workarea ] &&
rm -r $workarea

mkdir -vp $workarea
echo

echo "[$me] Initial file listing"
ls

binary=ProtoMol_r1935_tpr_topo_pdb_coords
echo "[$me] Ensuring core is present"
[ ! -f $binary ] &&
wget "http://www.nd.edu/~rnowling/$binary"
chmod a+x $binary

echo "[$me] Moving required files into $workarea"
mv -v $requiredFiles $workarea
cd $workarea

echo "[$me] Workarea:"
ls

echo "[$me] Above:"
ls ../

echo "[$me] Running simulation"
../with-env ../env.sh ../$binary protomol.conf &>my_md_logfile.txt

if [ $? -eq 0 ]; then
    echo SUCCESS >> my_md_logfile.txt
    mkdir output
    mkdir output/traj
    mv *xtc output/traj
    echo "[$me] Assigning trajectory to MSM states"
    mkdir Data
    cp -v ../Gens.lh5 Data
    cp -v ../AtomIndices.dat .
    ../with-env ../env.sh ConvertDataToHDF.py -s ../state0.pdb -I output
    ../with-env ../env.sh Assign.py
    ../with-env ../env.sh ConvertAssignToText.py
#else
#    exit 1
fi



echo "[$me] result files"
ls

echo "[$me] Compressing results"
resultfile=result.tar.bz2
tar cjfv $resultfile *.energy* *.pdb  my_md_logfile.txt Data/discrete.traj Data/tCounts.UnSym.mtx output/*
cd ..
mv -v $workarea/$resultfile .

echo "[$me] Cleaning up"
rm -rv $workarea
