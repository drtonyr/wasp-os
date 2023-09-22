# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2020 Daniel Thompson

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

import wasp

import fonts.clock as digits

DIGITS = (
        digits.clock_0, digits.clock_1, digits.clock_2, digits.clock_3,
        digits.clock_4, digits.clock_5, digits.clock_6, digits.clock_7,
        digits.clock_8, digits.clock_9
)

MONTH = 'JanFebMarAprMayJunJulAugSepOctNovDec'

class TideClockApp():
    """Simple digital clock application."""
    NAME = 'Tide Clock'

    def foreground(self):
        """Activate the application.

        Configure the status bar, redraw the display and request a periodic
        tick callback every second.
        """
        wasp.system.bar.clock = False
        self._draw(True)
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

    def _day_string(self, now):
        """Produce a string representing the current day"""
        # Format the month as text
        month = now[1] - 1
        month = MONTH[month*3:(month+1)*3]

        return '{} {} {}'.format(now[2], month, now[0])

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
            draw.blit(digits.clock_colon, 2*48, 55)

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
        draw.string(self._day_string(now), 40, 8, width=160)
        draw.blit(DIGITS[now[4]  % 10], 4*48, 56)
        draw.blit(DIGITS[now[4] // 10], 3*48, 56)
        draw.blit(DIGITS[now[3]  % 10], 1*48, 56)
        draw.blit(DIGITS[now[3] // 10], 0*48, 56)
        draw.string('20:14 Low 3.5h', 0, 144, width=240)
        draw.string('02:10 High 11.5h', 0, 168, width=240)
        draw.string('08:06 Low  17.5h', 0, 192, width=240)
        draw.string('14:02 High 23.5h)', 0, 216, width=240)

        # Record the minute that is currently being displayed
        self._min = now[4]
