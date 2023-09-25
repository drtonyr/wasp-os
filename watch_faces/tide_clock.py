# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2023 Tony Robinson

"""Digital clock with next tide times
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This app shows the time (as HH:MM) together with a battery meter, the date and the next four tides.  Swipe up for settings.

For coastal sites the tide times are highly predictable as they are driven by moon and sun positions which are in themselves highly predictable.  Once one high or low tide is set the predictions are good to within about 15 minutes.

Estuaries are far more complex, setting the next high and low tides will often give good predictions for near-coastal sites, but is unlikely to work for near freshwater sites.

If it's important then use a source specific to your location such as:

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
import wasp

import fonts.clock as digits

DIGITS = (
        digits.clock_0, digits.clock_1, digits.clock_2, digits.clock_3,
        digits.clock_4, digits.clock_5, digits.clock_6, digits.clock_7,
        digits.clock_8, digits.clock_9
)

MONTH = 'JanFebMarAprMayJunJulAugSepOctNovDec'

NTIDE = 4 # number of High/Low tide to display

# set MICROPY to be True and assume running on watch, else False and running in sim
# MICROPY = len(dir(time)) == 16

class TideClockApp():
    """Simple digital clock application."""
    NAME = 'Tide Clock'

    def __init__(self):
        # self.t0 = time.mktime((2019, 1, 1, 0, 0, 0, -1, -1))
        self.t0 = time.mktime((2019, 1, 1, 0, 0, 0, -1, -1, 0))
        self.nlocation = 0
        self._load_location()

    def _load_location(self):
        nlocation = 0
        self.location = None

        with open('data/TideClock.txt') as f:
            for line in f:
                if not line.startswith('#'):
                    if nlocation == self.nlocation:
                        data = line.strip().split(',')
                        self.location = data[0]
                        self.wavedata = [ int(item) for item in data[1:] ]
                        break
                    nlocation += 1
        # if self.nlocation not found then wrap
        if not self.location:
            self.nlocation = 0
            self._load_location()

        # we've changed location so no longer have any stored timestamps
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
            self.nlocation += 1
            self._load_location()
            self._draw(True)
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
        month = MONTH[3*now[1]-3:3*now[1]]
        draw.string("{} {} '{}".format(now[2], month, now[0] % 100), 40, 8, width=160)
        draw.blit(DIGITS[now[4]  % 10], 4*48, 48)
        draw.blit(DIGITS[now[4] // 10], 3*48, 48)
        draw.blit(DIGITS[now[3]  % 10], 1*48, 48)
        draw.blit(DIGITS[now[3] // 10], 0*48, 48)

        # check that we have valid timestamps for next tides, update if not
        rtcTime = wasp.watch.rtc.time()
        if not self.timestamp or rtcTime > self.timestamp[0][0]:
          period = 44714.16432
          # use fixed point arithmatic to get an integer base
          base = rtcTime - (((rtcTime - self.t0 + self.wavedata[0]) * 100000) % 4471416432) // 100000 + int(period)
          high = True
          if (base - rtcTime) / period > 0.5:
            high = False
            base -= int((period + 0.5) / 2)
          self.timestamp = []
          for i in range(NTIDE):
            self.timestamp.append((base, high))
            base += int((period + 0.5) / 2)
            high = not high

        # display the current location and the percentage of high tide
        part = (self.timestamp[0][0] - rtcTime) / (self.timestamp[1][0] - self.timestamp[0][0])
        if self.timestamp[1][1]:
          part = 1 - part
        percent = ' %0.f%%' % (50 * math.cos(math.pi * part) + 50)
        x = 240 - draw.bounding_box(percent)[0]
        chunk = draw.wrap(self.location, x)
        draw.string(self.location[:chunk[1]].strip(), 0, 120, width=x, right=False)
        draw.string(percent, x, 120)

        for i in range(NTIDE):
          y = 145 + 24 * i
          tstamp = self.timestamp[i][0]
          h, m = time.localtime(tstamp)[3:5]
          draw.string('%s' % ('High' if self.timestamp[i][1] else 'Low'), 5, y, width=75, right=False)
          draw.string('%02d:%02d' % (h, m), 80, y, width=80)
          draw.string('%0.1fh' % ((tstamp - rtcTime) / 3600), 165, y, width=75, right=True)

        # Record the minute that is currently being displayed
        self._min = now[4]
