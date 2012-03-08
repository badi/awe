
from util import typecheck, returns
import aweclasses
import mdtools

import numpy as np
import itertools
import time


class IResampler(object):

    """
    Interface that all resampling methods should implement
    """

    def resample(self, walkers):
        """
        Parameters:
          *walkers* : an object of type awe.aweclasses.WalkerGroup

        Returns:
          a new awe.aweclasses.WalkerGroup instance
        """

        raise NotImplementedError

    @typecheck(aweclasses.System)
    @returns(aweclasses.System)
    def __call__(self, s1):
        print time.asctime(), 'Resampling'

        print 's1', s1
        for c in s1.cells:
            print '\t', c
            print '\t\t', c.walkers

        s2 = self.resample(s1)

        print 's2', s2
        for c in s2.cells:
            print '\t', c
            print '\t\t', c.walkers

        return s2

class Identity(IResampler):

    """
    the identity function
    """

    def resample(self, walkers):
        return walkers


class OneColor(IResampler):

    """
    A single/no color algorithm based on Eric Darve and Ernest Ryu's:
      "Computing reaction rates in bio-molecular systems using discrete macro-states"
    """

    def __init__(self, targetwalkers):
        self.targetwalkers = targetwalkers

    def resample(self, system):

        from numpy import floor, argsort, random, sum

        newsystem = system.clone()
        state = system.as_state()

        for cell in system.cells:
            # print 'Processing cell', cell

            ### initialize the list of weights for walkers in the current cell
            localstate = state.slice_by(state.cells == cell.id)
            weights    = localstate.weights
            walkers    = localstate.walkers

            ### sort the walkers in descending order based on their weights,
            ##+ this ensures only walkers whose weight > targetWeight are split.
            mywalkers = list(argsort(-weights))
            # print '\tmywalkers:', mywalkers

            ### sanity check
            testmaxw = float('inf')
            for i in mywalkers:
                myw = weights[i]
                assert myw == weights[i], 'Weights mismatch'
                assert myw <= testmaxw, 'Weights non-monotonically decreasing'
                testmaxw = myw

            ### setup cell weight and target weights
            W     = sum(weights)
            tw    = W / self.targetwalkers
            # print '\tW', W, 'tw', tw

            newcell = aweclasses.Cell(cell.id, weight=tw, color=cell.color)

            ### we assume that there is at least one walker in the cell
            x = mywalkers.pop()

            ### keep track of active walkers for splitting
            activewalkers = 0

            ### The algorithm terminates since the last walker removed
            ##+ from 'mywalkers' when W == tw. The max number of
            ##+ iterations is bounded by 'len(where(system.cell == cell) + targetwalkers'
            while True: # exit using break

                Wx = weights[x]
                currentWalker = localstate.walker(x)
                # print '\tweight of', x, 'is', Wx

                ### split
                if Wx > tw or len(mywalkers) == 0:

                    ### choose number of times to split
                    ##+ r = floor( Wx / tw )
                    ### min, max: work around round-off errors
                    r = max(1, int(floor( Wx/tw )) )
                    r = min(r, self.targetwalkers - activewalkers)
                    activewalkers += r
                    # print '\tactive walkers', activewalkers

                    ### split the current walker
                    # print '\tsplitting', x, r, 'times'
                    for _ in itertools.repeat(x, r):
                        w = aweclasses.Walker(start=currentWalker.end)
                        newcell.add_walker(w)

                    ### update the weights for the current walker and mark
                    ##+ for reconsideration
                    if activewalkers < self.targetwalkers and Wx - r * tw > 0.0:
                        mywalkers.append(x)
                        weights[x] = Wx - r * tw
                        # print '\tupdated weights of', x

                    ### continue the loop?
                    if len(mywalkers) > 0:
                        x = mywalkers.pop()
                    else: break

                ### merge
                else:
                    y = mywalkers.pop()
                    # print '\tmerging', x, y
                    Wy = weights[y]
                    Wxy = Wx + Wy
                    p = np.random.random()
                    if p < Wy / Wxy:
                        x = y
                    weights[x] = Wxy

            newsystem.add_cell(newcell)

        return newsystem

class MultiColor(OneColor):

    def resample(self, system):

        newsystem = aweclasses.System(topology=system.topology)
        for color in system.colors:
            thiscolor  = system.filter_by_color(color)
            resampled  = OneColor.resample(self, thiscolor)
            newsystem += resampled
        return newsystem


class IPlotter(IResampler):

    def __init__(self, **kws):
        self.plotfile = kws.pop('plotfile', 'plot.png')

    def compute(self, walkergroup):
        raise NotImplementedError

    def plot(self):
        raise NotImplementedError

    def __call__(self, walkers):
        ws = IResampler.__call__(self, walkers)
        self.compute(ws)
        self.plot()
        return ws


class OneColor_SaveWeights(OneColor):

    def __init__(self, nwalkers, datfile='weights.dat'):
        OneColor.__init__(self, nwalkers)
        self.datfile   = datfile
        self.iteration = 0

    def saveweights(self, group, mode='a'):
        print 'Saving weights to', self.datfile

        ### all the walkers in a cell have the same weight, so we only
        ### need to save the (iteration, cell, weight) triples
        cells   = np.array(list(set(group.cells)))
        iters   = self.iteration * np.ones(len(cells))
        weights = -1 * np.ones(len(cells))
        for c in cells:
            ixs        = np.where(group.cells == c)
            walkers    = group.getslice(ixs)
            w          = walkers.weights[0] ### assume at least one walker per cell
            weights[c] = w
        assert weights.min() >= 0
        vals = np.vstack( (iters, cells, weights) )

        with open(self.datfile, mode) as fd:
            np.savetxt(fd, vals.T)

    def resample(self, walkergroup):
        if self.iteration == 0:
            self.saveweights(walkergroup, mode='w')

        newgroup         = OneColor.resample(self, walkergroup)
        self.iteration  += 1
        self.saveweights(newgroup)

        return newstate
