
import awe

import numpy as np


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
        return self.vals[:self._count]

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


        self._task_times            = ExtendableArray()  # keep track of the times values are added
        self._wq_times              = ExtendableArray()

        ### task stats
        self.computation_time       = Statistics()
        self.total_bytes_transfered = Statistics()
        self.total_transfer_time    = Statistics()
        self.task_run_time          = Statistics()       # WQ Task.finish_time - Task.start_time
        self.task_life_time         = Statistics()       # WQ Task.finish_time - Task.submit_time

        ### wq stats
        self.workers_ready          = Statistics()
        self.workers_busy           = Statistics()
        self.tasks_running          = Statistics()
        self.tasks_waiting          = Statistics()
        self.tasks_complete         = Statistics()
        self.total_tasks_dispatched = Statistics()
        self.total_tasks_complete   = Statistics()
        self.total_workers_joined   = Statistics()
        self.total_workers_removed  = Statistics()
        self.total_bytes_sent       = Statistics()
        self.total_bytes_recieved   = Statistics()
        self.total_send_time        = Statistics()
        self.total_receive_time     = Statistics()


    def task(task):
        """
        Update the running statistics with a task result
        """
        times = time.time() * np.ones(len(times))
        self._task_times.append(*times)

        self.computation_time       .update(task.computation_time)
        self.total_bytes_transfered .update(task.total_bytes_transfered)
        self.total_transfer_time    .update(task.total_transfer_time)
        self.task_run_time          .update(task.finish_time - task.start_time)
        self.task_life_time         .update(taslk.finish_time - task.submit_time)

    def wq(q):

        times = time.time() * np.ones(len(times))
        self._wq_times.append(*times)

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
        self.total_bytes_recieved   .update(q.total_bytes_recieved)
        self.total_send_time        .update(q.total_send_time)
        self.total_receive_time     .update(q.total_receive_time)


class AWEStats(object):

    def __init__(self):

        self.iteration_timer  = Timer()
        self.iteration_times  = ExtendableArray()
        self.iteration_values = ExtendableArray()

        self.resample_timer   = Timer()
        self.resample_times   = ExtendableArray()
        self.resample_values  = ExtendableArray()

        self.barrier_timer    = Timer()
        self.barrier_times    = ExtendableArray()
        self.barrier_values   = ExtendableArray()


    def timeit(self, state, timer, times, values):
        """
        *state* = {start|stop}
        """

        if state.lower() == 'start':
            timer.start()
        elif state.lower() == 'stop':
            timer.stop()
            times.append(time.time())
            values.append(timer.elapsed())
        else:
            raise ValueError, 'Unknown state %s: valid: {start|stop}' % state

    def time_iter(self, state):
        self.timeit(state, self.iteration_timer, self.iteration_times, self.iteration_values)

    def time_resample(self, state):
        self.timeit(state, self.resample_timer, self.resample_times, self.resample_values)

    def time_barrier(self, state):
        self.timeit(state, self.barrer_timer, self.barrer_times, self.barrer_values)
