# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2023 Tony Robinson

"""Digital clock with next tide times
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This app shows the time (as HH:MM) together with a battery meter, the date and the next four tides.  Swipe up for settings.

For coastal sites the tide times are highly predictable as they are driven by moon and sun positions which are in themselves highly predictable.  Once one high or low tide is set the predictions are good to within about 15 minutes.

Estuaries are far more complex, setting the next high and low tides will often give good predictions for near-coastal sites, but is unlikely to work for near freshwater sites.

If it's important then use a source specific to your site such as:

https://easytide.admiralty.co.uk/
https://ntslf.org/tides/predictions/
https://www.tidetimes.org.uk/
https://www.tidetimes.co.uk/
https://www.tidetime.org/

.. figure:: res/screenshots/TideApp.png
    :width: 179
"""

import math
import time
import array

import wasp
import fonts.clock as digits

_DIGITS = (
        digits.clock_0, digits.clock_1, digits.clock_2, digits.clock_3,
        digits.clock_4, digits.clock_5, digits.clock_6, digits.clock_7,
        digits.clock_8, digits.clock_9
)

_MONTH = 'JanFebMarAprMayJunJulAugSepOctNovDec'

_NTIDE = 4 # number of High/Low tide to display

_CONFIG = 'config.txt'

class Tide():
    def __init__(self, config: str, site: str) -> None:
        init = (2025, 1, 1, 0, 0, 0, 0, 0)
        if 'tzname' in dir(time):
            # running python or on host, likely 1735689600 from 1Jan1970
            self.t0 = int(time.mktime(init + (0,)))
        else:
            # running micropython on board, likely 789004800 from 1Jan2000
            self.t0 = time.mktime(init)
        self.basePeriod100 = 4471416 # 100 times M2 so that we can represent as an int
        self.basePeriod = int(round(self.basePeriod100 / 100)) # M2 in seconds
        self.halfPeriod = int(round(self.basePeriod100 / 200))
        self.period = array.array('I', [
            1275721,  # 2551442.9/2, # half synodic month 
            2380713,  # 2380713.2,   # anomalistic month
            2748551,  # 2748551.4,   # lunar evection
            1180292,  # 2360584.7/2, # half tropical month
            637861,   # 2551442.9/4, # quarter synodic month
            613005,   # unknown   7 days 5 hours 42 minutes
            871276 ]) # unknown  10 days 2 hours 1 minute
        for line in open(config, 'r'):
            # ideally this would be a json.read but micropython runs out of RAM
            if line.split(',', 1)[0] == site:
                word = line.split(',')
                self.offset = int(word[1])
                self.lowf   = float(word[2]) / 100
                self.s = array.array('f', [ float(s) for s in word[3:-1:2] ])
                self.c = array.array('f', [ float(s) for s in word[4:-1:2] ])
                self.error = int(word[-1])
                break
        else:
            raise Exception("site: %s not found in config: %s" % (site, config))
      
    def high(self, t: int) -> int:
        time0 = t - self.t0 - self.offset + self.halfPeriod
        base = time0 - (time0 % self.basePeriod100) % self.basePeriod + self.offset
        offset = 0.0
        for i in range(len(self.period)):
            omega = (base % self.period[i]) * (2.0 * math.pi / self.period[i])
            offset += self.s[i] * math.sin(omega) + self.c[i] * math.cos(omega)
        return self.t0 + base + int(offset)
    
    def low(self, t: int, lastHigh: bool = None, nextHigh: bool = None) -> int:
        if lastHigh == None:
            lastHigh = self.high(t - self.halfPeriod) 
        if nextHigh == None:
            nextHigh = self.high(t + self.halfPeriod) 
        return lastHigh + int(self.lowf * (nextHigh - lastHigh))
    
    def event(self, t: int, next: bool = False) -> tuple[int, bool]:
        if next == True:
            t += self.halfPeriod
        lastHigh = self.high(t)
        if lastHigh > t:
            nextHigh = lastHigh
            lastHigh = self.high(nextHigh - self.basePeriod)
        else:
            nextHigh = self.high(lastHigh + self.basePeriod)
        low = self.low(None, lastHigh=lastHigh, nextHigh=nextHigh)

        return min([(lastHigh, True), (low, False), (nextHigh, True)], key=lambda x: abs(x[0] - t))

## displayTime() and standardTime()
#
# adds and removes the daylight saving adjustment for Europe until 2099
# see https://en.wikipedia.org/wiki/Daylight_saving_time_by_country and
# https://github.com/orgs/micropython/discussions/11173#discussioncomment-6073759

# a version of mktime that works with Python and Micropython
def _mktime(base):
    nbase = 9 if 'tzname' in dir(time) else 8
    return time.mktime(base + (0,) * (nbase - len(base)))

# takes a standard time and adds any daylight saving adjustment for a few places
def _displayTime(t, region='Europe', offset=3600):
    year = time.localtime(t)[0]
    yoff = (5 * year) // 4
    if region == None:
        return t
    if region == 'Europe':
        springFwd = _mktime((year,3 ,31-(yoff+4)%7,1))  # Last Sunday in March
        fallBack  = _mktime((year,10,31-(yoff+1)%7,1))  # Last Sunday in October
    elif region == 'US-Canada':
        springFwd = _mktime((year,3 ,7-(yoff+1)%7,2))  # Second Sunday in March
        fallBack  = _mktime((year,11,7-(yoff+1)%7,2))  # First Sunday in November
    else:
        raise ValueError
      
    if t < springFwd or t > fallBack:
        return t
    else:
        return t + offset

# takes a display time and removes any daylight saving adjustment for Europe
# note that the answer for 1am to 2pm on the last Sunday in October is not defined
def _standardTime(t, region='Europe'):
    return _displayTime(t, region=region, offset=-3600)

  
class TideClockApp():
    """Digital clock application with tide times for the UK and Ireland."""
    NAME = 'Tide Clock'

    def __init__(self):
        self._nsite = 0
        self._load_nsite()

    def _load_nsite(self):
        with open(_CONFIG) as f:
            for n, line in enumerate(f):
                if n == self._nsite:
                    break
            else:
                self._nsite = 0
                f.seek(0)
                line = f.readline()
              
        # now have line, so set site
        self.site = line.split(',', 1)[0]
        
        # find the next site
        self._model = Tide(_CONFIG, self.site)

        # we've got a new site so flush any stored timestamps
        self.timestamp = None
        
    def foreground(self):
        """Activate the application.

        Configure the status bar, redraw the display and request a periodic
        tick callback every second.
        """
        wasp.system.bar.clock = False
        self._draw(True)
        wasp.system.request_event(wasp.EventMask.SWIPE_UPDOWN)
        wasp.system.request_tick(1000)        

    def sleep(self):
        """Prepare to enter the low power mode.

        :returns: True, which tells the system manager not to automatically
                  switch to the default application before sleeping.
        """
        return True

    def wake(self):
        """Return from low power mode.

        Time will have changes whilst we have been asleep so we must
        udpate the display (but there is no need for a full redraw because
        the display RAM is preserved during a sleep.
        """
        self._draw()

    def tick(self, ticks):
        """Periodic callback to update the display."""
        self._draw()

    def preview(self):
        """Provide a preview for the watch face selection."""
        wasp.system.bar.clock = False
        self._draw(True)

    def swipe(self, event):
        if event[0] == wasp.EventType.DOWN:
            self._nsite += 1
            self._load_nsite()
            # fudge to have immediate overwrite without clearing everything
            wasp.system.request_tick(1000)        
            self._min -= 1
            self._draw()
        else:
            return True            
     
    def _draw(self, redraw=False):
        """Draw or lazily update the display.

        The updates are as lazy by default and avoid spending time redrawing
        if the time on display has not changed. However if redraw is set to
        True then a full redraw is be performed.
        """
        draw = wasp.watch.drawable

        if redraw:
            now = wasp.watch.rtc.get_localtime()

            # Clear the display and draw that static parts of the watch face
            draw.fill()
            draw.blit(digits.clock_colon, 2*48, 40)

            # Redraw the status bar
            wasp.system.bar.draw()
        else:
            # The update is doubly lazy... we update the status bar and if
            # the status bus update reports a change in the time of day 
            # then we compare the minute on display to make sure we 
            # only update the main clock once per minute.
            now = wasp.system.bar.update()
            if not now or self._min == now[4]:
                # Skip the update
                return

        # Draw the changeable parts of the watch face
        # This is the standard time and date, the date is squeezed in at
        # the top and the time just below it
        month = _MONTH[3*now[1]-3:3*now[1]]
        draw.string("{} {} '{}".format(now[2], month, now[0] % 100), 40, 8, width=160)
        draw.blit(_DIGITS[now[4]  % 10], 4*48, 48)
        draw.blit(_DIGITS[now[4] // 10], 3*48, 48)
        draw.blit(_DIGITS[now[3]  % 10], 1*48, 48)
        draw.blit(_DIGITS[now[3] // 10], 0*48, 48)

        # check that we have valid timestamps for next tides, update if not
        utcTime = _standardTime(int(wasp.watch.rtc.time()))
        if not self.timestamp or utcTime > self.timestamp[0][0]:
            base, high = self._model.event(utcTime)
            if base < utcTime:
                base, high = self._model.event(base, next=True)
            self.timestamp = [(base, high)]
            for i in range(1, _NTIDE):
                base, high = self._model.event(base, next=True)
                self.timestamp.append((base, high))

        # display the current site and the percentage of high tide
        part = (self.timestamp[0][0] - utcTime) / (self.timestamp[1][0] - self.timestamp[0][0])
        if self.timestamp[1][1]:
            part = 1 - part
        percent = ' %0.f%%' % (50 * math.cos(math.pi * part) + 50)
        x = 240 - draw.bounding_box(percent)[0]
        chunk = draw.wrap(self.site, x)
        draw.string(self.site[:chunk[1]].strip(), 0, 120, width=x, right=False)
        draw.string(percent, x, 120)

        for i in range(_NTIDE):
            y = 145 + 24 * i
            tstamp = self.timestamp[i][0]
            h, m = time.localtime(_displayTime(tstamp))[3:5]
            draw.string('%s' % ('High' if self.timestamp[i][1] else 'Low'), 5, y, width=75, right=False)
            draw.string('%02d:%02d' % (h, m), 80, y, width=80)
            draw.string('%0.1fh' % ((tstamp - utcTime) / 3600), 165, y, width=75, right=True)

        # Record the minute that is currently being displayed
        self._min = now[4]
