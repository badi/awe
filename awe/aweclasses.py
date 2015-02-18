# -*- mode: Python; indent-tabs-mode: nil -*-  #
"""
This file is part of AWE
Copyright (C) 2012- University of Notre Dame
This software is distributed under the GNU General Public License.
See the file COPYING for details.
"""

import io, stats, workqueue
from util import typecheck, returns
import structures, util

import trax
import mdprep

import numpy as np
import cPickle as pickle

import os, time, shutil
from collections import defaultdict
import shutil


_WALKER_ID = 0
_DEFAULT_COLOR = -1
DEFAULT_CORE = -1

class SimState(object):

    def __init__(self, x=None, v=None, t=None):
        """
        Input:
          - x: :: NxD array of positions
          - v: :: NxD array of velocities
          - t  :: float time
        """
        assert x is not None
        assert v is not None
        assert x.shape == v.shape
        t = 0 if t is None else t
        self.x, self.v, self.t = x, v, t

    def __eq__(self, other):
        return self.x == other.x \
          and  self.v == other.v \
          and  self.t == other.t

    def to_gps(self):
        x = mdprep.gps.array2str(self.x)
        v = mdprep.gps.array2str(self.v)
        t = mdprep.gps.scalar2str(self.t)
        return x, v, t

    @classmethod
    def from_gps(cls, xstr, vstr, tstr):
        x = mdprep.gps.str2array(xstr)
        v = mdprep.gps.str2array(vstr)
        t = mdprep.gps.str2scalar(tstr, float)
        return cls(x=x, v=v, t=t)

    def __len__(self):
        "Number of atoms"
        return len(self.x)

    @property
    def dim(self):
        return self.x.shape[-1]

    def fuzz(self):
        return self.__class__(x=self.x,
                              v=self.v + np.random.random(self.v.shape),
                              t=self.t)
        

class Walker(object):

    """
    Capture the state of a single walker.
    This include the starting and ending coordinates, and it's assignment

    Relevant fields are:

      *start*      : starting state
      *end*        : ending state
      *assignment* : int
    """

    def __init__(self, start=None, end=None, assignment=None, color=_DEFAULT_COLOR, weight=None, wid=None, cellid=None, initid=None):

        assert not (start is None and end is None), 'start = %s, end = %s' % (start, end)

        self._start      = start
        self._end        = end
        self._assignment = assignment
        self._color      = color
        self._weight     = weight
        self._cellid     = cellid

        if wid is None:
            global _WALKER_ID
            self._id     = _WALKER_ID
            _WALKER_ID  += 1
        else:
            self._id     = wid

        self._initid    = initid or self._id

    def __eq__(self, other):
        if not type(self) is type(other):
            return False

        return \
            (self._start     == other._start).all() and \
            self._assignment == other._assignment   and \
            self._color      == other._color        and \
            self._weight     == other._weight


    def restart(self, weight=None, cellid=None):
        assert self._start is not None
        assert self._end   is not None
        assert weight      is not None

        global _WALKER_ID
        wid =  _WALKER_ID
        _WALKER_ID += 1

        cid = cellid or self._cellid

        return Walker(start      = self._end.fuzz(),
                      end        = None,
                      assignment = self._assignment,
                      color      = self._color,
                      weight     = weight,
                      wid        = wid,
                      cellid     = cid,
                      initid     = self._initid)


    @property
    def id(self):         return self._id

    @property
    def cellid(self):     return self._cellid

    @property
    def initid(self):    return self._initid

    @property
    def start(self):      return self._start

    @property
    def end(self):        return self._end

    @end.setter
    def end(self, crds):  self._end = crds

    @property
    def assignment(self): return self._assignment

    @assignment.setter
    def assignment(self, asn):   self._assignment = asn

    @property
    def color(self):      return self._color

    @color.setter
    def color(self, c):   self._color = c

    @property
    def weight(self):     return self._weight

    @property
    def natoms(self):     return len(self._coords)

    @property
    def ndim(self):       return self._coords.dim

    @property
    def _coords(self):
        if self.start is not None:
            return self.start
        elif self.end is not None:
            return self.end
        else: raise ValueError, 'Both *start* and *end* should not be None'


    def __str__(self):
        return '<Walker: id=%(id)d, size=%(size)d, dim=%(dim)d, assignment=%(assignment)d, color=%(color)s, weight=%(weight)s>' \
            % {'id' : self.id, 'size'   : self.natoms, 'dim' : self.ndim,
               'assignment' : self.assignment, 'color' : self.color,
               'weight' : self.weight}

    def __repr__(self): return str(self)




class AWE(object):

    """
    The main driver for the Accelerated Weighted Ensemble algorithm.
    This class manages the marshaling of workers to/from workers,
    updating the current WalkerGroup, and calling the resampleing
    algorithm.
    """

    # @typecheck(wqconfig=workqueue.Config, system=System, iterations=int)
    def __init__(self, wqconfig=None, system=None, iterations=-1, resample=None,
                 traxlogger = None, checkpointfreq=1):

        self._print_start_screen()
        
	self.statslogger = stats.StatsLogger('debug/task_stats.log.gz')
        self.transitionslogger = stats.StatsLogger('debug/cell-transitions.log.gz')

        self.wq         = workqueue.WorkQueue(wqconfig, statslogger=self.statslogger)
        self.system     = system
        self.iterations = iterations
        self.resample   = resample

        self.iteration  = 0

	self.currenttask = 0

        self.stats      = stats.AWEStats(logger=self.statslogger)

        self.traxlogger = traxlogger or trax.SimpleTransactional(checkpoint = 'debug/trax.cpt',
                                                                 log        = 'debug/trax.log')
        self.checkpointfreq = checkpointfreq

        self._firstrun  = True

    def _print_start_screen(self):
        start_str = "********************************* AWE - Acclerated Weighted Ensemble *******************************\n"
        start_str += "AUTHORS:\n"
        start_str += "  Badi' Abdul-Wahid\n"
        start_str += "  Haoyun Feng\n"
        start_str += "  Jesus Izaguirre\n"
        start_str += "  Eric Darve\n"
        start_str += "  Ronan Costaouec\n"
        start_str += "  Dinesh Rajan\n"
        start_str += "  Douglas Thain\n"
        start_str += "\n"
        start_str += "CITATION:\n"
        start_str += "  Badi Abdul-Wahid, Li Yu, Dinesh Rajan, Haoyun Feng, Eric Darve, Douglas Thain, Jesus A. Izaguirre,\n"
        start_str += "  Folding Proteins at 500 ns/hour with Work Queue,\n"
        start_str += "  8th IEEE International Conference on eScience (eScience 2012), October, 2012.\n"
        start_str += "\n"
        start_str += "WEB PAGE:\n"
        start_str += "  www.nd.edu/~ccl/software/awe\n"
        start_str += "***************************************************************************************************\n"

        print start_str

    def checkpoint(self):
        cpt = self.traxlogger.cpt_path
        if os.path.exists(cpt):
            shutil.move(cpt, cpt + '.last')
        chk = dict(system         = self.system,
                   iterations     = self.iterations,
                   iteration      = self.iteration,
                   resample       = self.resample,
                   checkpointfreq = self.checkpointfreq
                   )
        chk['_firstrun'] = self._firstrun
        self.traxlogger.checkpoint(chk)


    def logwalker(self, walker):
        self.traxlogger.log(walker)

    def _trax_log_recover(self, obj, value):
        print 'Recovering walker', value.id
        obj['system'].set_walker(value)

    def recover(self):
        cpt = self.traxlogger.cpt_path
        if os.path.exists(cpt):
            print 'Recovering', cpt
            parms = self.traxlogger.recover(self._trax_log_recover)
            for a in parms.iterkeys():
                setattr(self, a, parms[a])

    def _submit(self):

        ws = self.system.walkers
        print time.asctime(), 'Submitting {} walkers'.format(len(ws))
        for walker in ws:
            if walker.end is None:
                task = self._new_task(walker)
                self.wq.submit(task)
        print time.asctime(), 'Done submitting walkers'


    # @typecheck(Walker)
    # @returns(workqueue.WQ.Task)
    def _new_task(self, walker):
	self.currenttask += 1
        task = self.wq.new_task()
        tag  = self.encode_task_tag(walker)
        task.specify_tag(tag)
        self.marshal_to_task(walker, task)
        return task

    def _try_duplicate_tasks(self):
        i = 0
        while self.wq.can_duplicate_tasks():
            i += 1
            if i > 20: break
            tag    = self.wq.select_tag()
            if tag is None: break
            wid    = self.decode_from_task_tag(tag)['walkerid']
            walker = self.system.walker(wid)
            task   = self._new_task(walker)
            self.wq.submit(task)

    def _recv(self):

        print time.asctime(), 'Receiving tasks'
        system = self.system
        self.stats.time_barrier('start')
        while not self.wq.empty:
            walker = self.wq.recv(self.marshal_from_task)
            system.set_walker(walker)
            self.logwalker(walker)
            self._try_duplicate_tasks()
        self.stats.time_barrier('stop')
        self.wq.clear()
        print system

    def _resample(self):

        self.stats.time_resample('start')
        self.system = self.resample(self.system)
        self.stats.time_resample('stop')
            

    def run(self):
        """
        Run the algorithm
        """

        self.recover()

        if self._firstrun:
            self.resample.save(self.system)
            self._firstrun = False

        assert len(self.system.cells  ) > 0
        assert len(self.system.walkers) > 0

        t = time.time()
        self.statslogger.update(t, 'AWE', 'start_unix_time', t)

        try:
            while self.iteration < self.iterations:

                if self.iteration % self.checkpointfreq == 0:
                    print time.asctime(), 'Checkpointing to', self.traxlogger.cpt_path
                    self.checkpoint()

                self.iteration += 1

                print time.asctime(), 'Iteration', self.iteration, 'with', len(self.system.walkers), 'walkers'
                runtime = stats.time.time()
                self.statslogger.update(runtime, 'AWE', 'iteration', self.iteration)
                self.statslogger.update(runtime, 'AWE', 'walkers', len(self.system.walkers))

                self.stats.time_iter('start')

                self._submit()
                self._recv()     ## barrier
                self._resample()

                self.stats.time_iter('stop')


        except KeyboardInterrupt:
            pass

        # except Exception, e:
        #     print 'Failed:', e
        #     import sys
        #     sys.exit(1)


    # @typecheck(int, int)
    # @returns(str)
    def encode_task_tag(self, walker):
        tag = '%(outfile)s|%(cellid)d|%(weight)f|%(walkerid)d' % {
            'outfile' : workqueue.RESULT_NAME,
            'cellid'  : walker.assignment,
            'weight'  : walker.weight,
            'walkerid' : walker.id}

        return tag

    @typecheck(str)
    @returns(dict)
    def decode_from_task_tag(self, tag):
        split = tag.split('|')
        outfile, cellid, weight, walkerid = tag.split('|')
        return {'cellid'   : int(cellid)   ,
                'weight'   : float(weight) ,
                'walkerid' : int(walkerid) ,
                'outfile'  : outfile       }

        

    def _task_files_dir(self, task):
        return os.path.join('debug', 'tasks')

    # @typecheck(int, workqueue.WQ.Task)
    def marshal_to_task(self, walker, task):
        
        tfd = self._task_files_dir(task)
        if not os.path.exists(tfd):
            os.makedirs(tfd)

        # xf, vf, tf = [os.path.join(tfd, '{}0.gps'.format(n)) for n in 'x v t'.split()]
        # for fn, dat in zip([xf, vf, tf], walker.start.to_gps()):
        #     with open(fn, 'w') as fd: fd.write(dat)
        #     task.specify_input_file(fn, os.path.basename(fn), cache=False)

        task.specify_input_file(self.system.topology, cache=True)

        x, v, t = walker.start.to_gps()
        task.specify_buffer(x, 'x0.gps', cache=False)
        task.specify_buffer(v, 'v0.gps', cache=False)
        task.specify_buffer(t, 't0.gps', cache=False)


        # ### create the pdb
        # top        = self.system.topology
        # top.coords = walker.start
        # pdbdat     = str(top)

        ### send walker to worker

        # with open(os.path.join(tfd, workqueue.WORKER_WALKER_NAME), 'wb') as fd:
        #     pickle.dump(walker, fd, protocol=pickle.HIGHEST_PROTOCOL)
        #     task.specify_input_file(fd.name, os.path.basename(fd.name), cache=False)

        wdat = pickle.dumps(walker)
        # task.specify_buffer(pdbdat, workqueue.WORKER_POSITIONS_NAME+"."+str(self.currenttask), cache=False)
        task.specify_buffer(wdat  , workqueue.WORKER_WALKER_NAME   , cache=False)

        ### specify output
        self.specify_task_output_file(task)

    def task_output_filename(self, task):
        tfd = self._task_files_dir(task)
        return os.path.join(tfd, task.tag)

    def specify_task_output_file(self, task):
        output = self.task_output_filename(task)
        # task.specify_output_file(output, remote_name = workqueue.WORKER_RESULTS_NAME+"."+str(self.currenttask), cache=False)
        task.specify_output_file(output, remote_name = workqueue.WORKER_RESULTS_NAME, cache=False)

    @typecheck(workqueue.WQ.Task)
    @returns(Walker)
    def marshal_from_task(self, result):

        import tarfile
        outfile = self.task_output_filename(result)
        tar = tarfile.open(outfile)
        try:
            x = tar.extractfile('x1.gps').read()
            v = tar.extractfile('v1.gps').read()
            t = tar.extractfile('t1.gps').read()
            walkerstr         = tar.extractfile(workqueue.WORKER_WALKER_NAME).read()
            # pdbstring         = tar.extractfile(workqueue.RESULT_POSITIONS).read()
            cellstring        = tar.extractfile(workqueue.RESULT_CELL     ).read()
        finally:
            tar.close()

        # pdb               = structures.PDB(pdbstring)
        # coords            = pdb.coords
        simstate          = SimState.from_gps(x, v, t)
        cellid            = int(cellstring)

        walker            = pickle.loads(walkerstr)

        transition = walker.assignment != cellid
        print time.asctime(), 'Iteration', self.iteration, '/', self.iterations, \
              'Walker', walker.id, \
              'transition', walker.assignment, '->', cellid, \
              self.wq.tasks_in_queue(), 'tasks remaining'
        self.transitionslogger.update(time.time(), 'AWE', 'cell_transition',
                                      'iteration %s from %s to %s %s' % \
                                          (self.iteration, walker.assignment, cellid, transition))

        walker.end        = simstate
        walker.assignment = cellid

        shutil.rmtree(self._task_files_dir(result))
        return walker





class Cell(object):

    def __init__(self, cid, weight=1., core=DEFAULT_CORE, walkers=None):
        self._id      = cid
        self._core    = core


    @property
    def id(self): return self._id

    @property
    def core(self): return self._core

    @property
    def color(self, wid):return self._walkers[wid].color

    def __str__(self):
        return '<Cell: %d, core=%s>' % \
            (self.id, self.core)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if type(other) is not type(self):
            return False

        return \
            self._id     == other._id     and \
            self._core   == other._core



class System(object):

    def __init__(self, topology=None, cells=None):
        self._topology = topology
        self._cells    = cells or dict()
        self._walkers  = dict()


    def __str__(self):
        return '<System: topology=%s, ncells=%s, nwalkers=%s>' % \
            (type(self.topology), len(self._cells), len(self._walkers))

    def __repr__(self):
        return 'System(topology=%r, cells=%r)' % (self._topology, self._cells)

    def __iadd__(self, other):
        self._cells.update(other._cells)
        self._walkers.update(other._walkers)

        return self


    @property
    def topology(self): return self._topology

    @property
    @returns(list)
    def cells(self):
        return self._cells.values()

    @property
    @returns(list)
    def walkers(self):
        return self._walkers.values()

    @property
    # @returns(np.array)
    def weights(self):
        return np.array(map(lambda w: w.weight, self.walkers))

    @property
    @returns(set)
    def colors(self):
        return set(map(lambda w: w.color, self.walkers))

    @typecheck(Cell)
    def add_cell(self, cell):
        if cell.id in self._cells:
            raise ValueError, 'Duplicate cell id %d' % cell.id
        self.set_cell(cell)

    @typecheck(Cell)
    def set_cell(self, cell):
        self._cells[cell.id] = cell

    @returns(Walker)
    def walker(self, wid):
        return self._walkers[wid]

    @typecheck(Walker)
    def add_walker(self, walker):
        assert walker.assignment >= 0, 'is: %s' % walker.assignment
        self.set_walker(walker)

    @typecheck(Walker)
    def set_walker(self, walker):
        self._walkers[walker.id] = walker

    @returns(Cell)
    def cell(self, i):
        return self._cells[i]

    @returns(bool)
    def has_cell(self, i):
        return i in self._cells

    # @returns(System)
    def filter_by_cell(self, cell):
        ws     = filter(lambda w: w.assignment == cell.id, self.walkers)
        newsys = self.clone(cells={cell.id:self.cell(cell.id)})
        for w in ws: newsys.add_walker(w)
        return newsys

    # @returns(System)
    def filter_by_color(self, color):
        ws     = filter(lambda w: w.color == color, self.walkers)
        newsys = self.clone()

        for w in ws:
            newsys.add_walker(w)

            cell = self.cell(w.assignment)
            newsys.set_cell(cell)

        return newsys


    # @returns(System)
    def filter_by_core(self, core):
        cells  = filter(lambda c: c.core == core, self.cells)
        cs     = {}
        for c in cells: cs[c.id] = c

        newsys = self.clone(cells=cs)
        for w in self.walkers:
            if w.assignment in cs:
                newsys.add_walker(w)

        return newsys

    def clone(self, cells=True):
        _cells = self._cells if cells else dict()
        return System(topology=self.topology, cells=_cells)


class SinkStates(object):

    def __init__(self):
        self._color_state = defaultdict(set)
        self._state_color = dict()

    def add(self, color, *states):
        for state in states:
            self._color_state[color].add(state)
            self._state_color[state] = color

    def color(self, cell):
        if cell.id in self._state_color:
            return self._state_color[cell.id]
        else:
            global _DEFAULT_COLOR
            return _DEFAULT_COLOR

    def states(self, color):
        return self._color_state[color]

    @property
    def ncolors(self): return len(self._color_state)
