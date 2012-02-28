
import awe

import numpy as np

import time


class Timer(object):
    def __init__(self):
        self.t0 = 0.
        self.t1 = float('inf')

    def start(self):
        self.t0 = time.time()

    def stop(self):
        self.t1 = time.time()

    def isrunning(self):
        return self.t0 > 0

    def elapsed(self, units='s'):
        mults      = {'s' : 1,
                      'm' : 60,
                      'h' : 60*60,
                      'd' : 60*60*24 }
        multiplier = mults[units]
        if self.t1 == float('inf'):
            t1 = time.time()
        else:
            t1 = self.t1
        diff       = t1 - self.t0
        return multiplier * diff

class NormTime(object):
    """
    Ensures that times start at 0
    """

    def __init__(self):
        self._timer = Timer()
        self._timer.start()

    def time(self):
        return self._timer.elapsed(units='s')

class ExtendableArray(object):
    """
    A numpy.array that can be efficiently appended to
    """

    def __init__(self, typ=np.zeros, size=500, factor=2):

        self._type    = typ
        self._size0   = size
        self._count   = 0
        self._factor  = factor
        self._vals    = self._initialize()

    def _initialize(self):
        return self._type(self._size0)

    def get(self):
        return self._vals[:self._count]

    def _realloc(self):

        if self._count == len(self._vals):

            x     = len(self._vals)
            alloc = x * self._factor
            vals2 = self._initialize(self._initial, alloc)
            vals2[:self._count] = self._vals[:self._count]
            self._vals = vals2


    def append(self, *values):

        i = self._count
        j = i + len(values)
        self._vals[i:j] = np.array(values)
        self._count += len(values)

    def __getitem__(self, i):
        assert i <= self._count
        return self._vals[i]

    def __setitem__(self, k, v):
        assert k <= self._count
        self._vals[k] = v

    def __len__(self):
        return self._count

    def __contains__(self, v):
        return v in self._vals[:self._count]

    def __iter__(self):
        return iter(self._vals[:self._count])

    def __str__(self):
        return str(self._vals[:self._count])

    def __repr__(self):
        return repr(self._vals[:self._count])
            

class Statistics(object):

    """
    Keep track of running statistics as the program runs
    """

    def __init__(self):

        self._num    = 0
        self._mean   = 0.
        self._m2     = 0.

        self._values = ExtendableArray() # keep track of the actual values for plots

    num  = property(lambda self: self._num)
    mean = property(lambda self: self._mean)
    var  = property(lambda self: self._m2 / float(self._num))
    std  = property(lambda self: math.sqrt(self.var))

    @property
    def values(self):
        return self._values.get()

    def update(self, *values):

        self._values.append(*values)

        for t in values:
            self._num += 1
            delta      = t - self._mean
            self._mean = self._mean + delta / float(self._num)
            self._m2   = self._m2 + delta * (t - self._mean)


    def __str__(self):
        return 'N = %s mean = %s std = %s' % (self.num, self.mean, self.std)



class WQStats(object):

    """
    Keep track of the WQ statistics
    """

    def __init__(self):

        self._task_times             = ExtendableArray()  # keep track of the times values are added
        self._ttime                  = NormTime()

        self._wq_times               = ExtendableArray()
        self._qtime                  = NormTime()

        ### task stats
        self.computation_time        = Statistics()
        self.total_bytes_transferred = Statistics()
        self.total_transfer_time     = Statistics()
        self.task_life_time          = Statistics()       # WQ Task.finish_time - Task.submit_time

        ### wq stats
        self.workers_init            = Statistics()
        self.workers_ready           = Statistics()
        self.workers_busy            = Statistics()
        self.tasks_running           = Statistics()
        self.tasks_waiting           = Statistics()
        self.tasks_complete          = Statistics()
        self.total_tasks_dispatched  = Statistics()
        self.total_tasks_complete    = Statistics()
        self.total_workers_joined    = Statistics()
        self.total_workers_removed   = Statistics()
        self.total_bytes_sent        = Statistics()
        self.total_bytes_received    = Statistics()
        self.total_send_time         = Statistics()
        self.total_receive_time      = Statistics()


    @awe.typecheck(awe.workqueue.WQ.Task)
    def task(self, task):
        """
        Update the running statistics with a task result
        """
        self._task_times.append(awe.time.time())

        self.total_bytes_transferred .update(task.total_bytes_transferred)

        # convert all times to seconds from microseconds
        self.computation_time        .update( task.computation_time                / 10.**6)
        self.total_transfer_time     .update( task.total_transfer_time             / 10.**6)
        self.task_life_time          .update((task.finish_time - task.submit_time) / 10.**6)

    @awe.typecheck(awe.workqueue.WQ.WorkQueue)
    def wq(self, wq):

        self._wq_times.append(awe.time.time())

        q = wq.stats

        self.workers_ready          .update(q.workers_ready)
        self.workers_busy           .update(q.workers_busy)
        self.tasks_running          .update(q.tasks_running)
        self.tasks_waiting          .update(q.tasks_waiting)
        self.tasks_complete         .update(q.tasks_complete)

        self.total_tasks_dispatched .update(q.total_tasks_dispatched)
        self.total_tasks_complete   .update(q.total_tasks_complete)
        self.total_workers_joined   .update(q.total_workers_joined)
        self.total_workers_removed  .update(q.total_workers_removed)
        self.total_bytes_sent       .update(q.total_bytes_sent)
        self.total_bytes_received   .update(q.total_bytes_received)

        # convert all times to seconds from microseconds
        self.total_send_time        .update(q.total_send_time    / 10.**6)
        self.total_receive_time     .update(q.total_receive_time / 10.**6)

    def save(self, wqstats, taskstats):
        """
        @param wqstats: path to save the wq stats to
        @param taskstats: path to save the task stats to
        """

        with open(wqstats, 'w') as fd:
            self._save_wq_stats(fd)

        with open(taskstats, 'w') as fd:
            self._save_task_stats(fd)


    def _save_attrs(self, fd, name, times, attrs):
        print 'Saving', name, 'data to', fd.name
        data = dict()
        data['time'] = times
        for a in attrs:
            print '\t', a
            data[a] = getattr(self, a).values
        np.savez(fd, **data)

    def _save_task_stats(self, fd):
        attrs = 'computation_time total_bytes_transferred total_transfer_time task_life_time'.split()

        self._save_attrs(fd, 'task', self._task_times.get(), attrs)

    def _save_wq_stats(self, fd):
        attrs =  'workers_ready workers_busy tasks_running tasks_waiting tasks_complete'.split()
        attrs += 'total_tasks_dispatched total_tasks_complete total_workers_joined'.split()
        attrs += 'total_workers_removed total_bytes_sent total_bytes_received'.split()
        attrs += 'total_send_time total_receive_time'.split()

        self._save_attrs(fd, 'wq', self._wq_times.get(), attrs)



class Timings(object):

    def __init__(self):
        self.timer = Timer()
        self.times = ExtendableArray()
        self.stats = Statistics()

    @property
    def data(self):
        return self.times.get(), self.stats.values

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.times.append(time.time())
        self.stats.update(self.timer.elapsed())


    def _save(self, fd, name):
        ts, vs = self.times.get(), self.stats.values
        vals = np.vstack( (ts, vs) )
        kws = {name : name}
        np.savez(fd, **kws)


    def save(self, target, name, mode='a'):
        """
        @param target: file handle or string
        """

        if type(target) is str:
            with open(target, mode) as fd:
                self._save(fd, name)
        else:
            self._save(target, name)


class AWEStats(object):

    def __init__(self):

        self.iteration = Timings()
        self.resample  = Timings()
        self.barrier   = Timings()

    @awe.typecheck(str, Timings)
    def _timeit(self, state, timings):
        """
        *state* = {start|stop}
        """

        if state.lower() == 'start':
            timings.start()
        elif state.lower() == 'stop':
            timings.stop()
        else:
            raise ValueError, 'Unknown state %s: valid: {start|stop}' % state

    def time_iter(self, state):
        self._timeit(state, self.iteration)

    def time_resample(self, state):
        self._timeit(state, self.resample)

    def time_barrier(self, state):
        self._timeit(state, self.barrier)

    def save(self, path):
        print 'Saving to', path
        with open(path, 'w') as fd:
            data = dict()

            print '\t','iteration data'
            ts, vs = self.iteration.data
            data['iteration_time'] = ts
            data['iteration_values'] = vs

            print '\t','resample data'
            ts, vs = self.resample.data
            data['resample_time'] = ts
            data['resample_values'] = vs

            print '\t','barrier data'
            ts, vs = self.barrier.data
            data['barrier_time'] = ts
            data['barrier_values'] = vs

            np.savez(fd, **data)
