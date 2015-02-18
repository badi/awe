# -*- mode: Python; indent-tabs-mode: nil -*-  #
"""
This file is part of AWE
Copyright (C) 2012- University of Notre Dame
This software is distributed under the GNU General Public License.
See the file COPYING for details.
"""

from io import trace, log
from util import typecheck, typecheckfn

import stats
import aweclasses
import workqueue
import io
import resample
import structures

from aweclasses import SimState, Walker, AWE, Cell, System, SinkStates
from workqueue import Config
from stats import time
from structures import PDB

import voronoi

import prody

### compatibility with different versions of prody
try:
    prody.setVerbosity('error')
except AttributeError:
    prody.confProDy(verbosity='error')

stats.time.start()
