# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2023 Tony Robinson

"""WASP Editor Eval
~~~~~~~~~~~~~~~~~~~

This is a tiny editor, complete with keyboard which can call Python exec().  Thus you can write notes or code on the watch and run it as well. It's written mostly for geek value, who else can run Python code on their watch?

There are two keyboard layouts, one contains lower case letters, numbers and some other characters, the other contains upper cases letters, commands and the rest of the character set.  Typing a 'key' is a two stage process, in the first stage the keyboard is pressed in the approximate location which results in a section of the keyboard being shown on the whole screen.  The desired letter is then pressed, or a swipe to dismiss all choices.  Four of the keys implement commands, although only 'exec' works at present.  The keyboard layout may be swapped buy a short swipe up on the keyboard, alternatively a swipe down to the keyboard swaps the layout and selects the region in one go.

The cursor is shown as an underscore, '_'.  A swipe left in the text areas moves the cursor left, a swipe moves the cursor right. A swipe left on the keyboard deletes the character to the left, a swipe right deletes the character to the right.

--- notes ---

We get 13 lines of 18 pixels and 6 left over.  The top 8 lines are text, the bottom 5 are keyboard.

Scrolling in the text area moves the cursor.  Ideally clicking in the
text area moves the cursor as well - that will take some calcuation.

Swipe left/right AND swipe up/down in the keyboard area cycles the
keyboard between upper case, lower case and command.

leftover 6 - 2 are used for bar at bottom.  Maybe use another 3/4 to indicate if there is text above and below the screen.  That is, if you can scroll up and see something not displayed, draw a solid line at the top - same for bottom only make it two lines.

    .. figure:: res/screenshots/EditExecApp.png
        :width: 179

        Screenshot of the EditExec application
"""

import io
import time
import wasp, array
from micropython import const
import fonts
import watch

# missing '!"#$%^&*()_',
layout = [ [ 'qwertyuiop"$789', "asdfghjkl:'-456", '!zxcvbnm,;/+123', """()?.     \n\n*%0="""],
           [ 'QWERTYUIOP<>\0', "ASDFGHJKL\\[]\0", '|ZXCVBNM@~{}\0', """_&^#     \n\n`\0""" ]]
cmd = [ 'Exec', 'Load', 'Save', 'Exit' ]

# check layout
# print('missing:', set(chr(n) for n in range(32, 127)).difference(set(sorted(''.join(''.join(page) for page in layout)))))

_fontTiny = fonts.sans18
fonth = 18
nsep = 164

class EditExecApp():
  NAME = 'EditExec'
  
  def __init__(self):
    self.text  = [ 'print("hello world")' ]
    self.xchar = len(self.text[0])
    self.ychar = 0
    self.output = ''
    self.mode = None
    self.page = 0
    
  def drawText(self, text, cursor=False):
    draw = wasp.watch.drawable
    draw.set_font(_fontTiny)
    draw.fill(x=0, y=0, w=240, h=nsep, bg=0x0000)

    # this assumes all lines fit on the screen
    nline = 0
    for line in text:
      if len(line) > 0:
        # if we want a cursor and it's on this line then add it
        if cursor and self.ychar == nline:
          line = line[:self.xchar] + '_' + line[self.xchar:]

        # only draw what fits - this should be
        chunk = draw.wrap(line, 240)
        draw.string(line[:chunk[1]], 0, nline * fonth)
      nline += 1

  def drawKbd(self):
    draw = wasp.watch.drawable
    draw.set_font(_fontTiny)

    draw.fill(x=0, y=nsep, w=240, h=1, bg=0xffff)
    draw.fill(x=0, y=nsep+1, w=240, h=240-nsep-1)
    for y, line in enumerate((layout[self.page])):
      for x, c in enumerate(line):
        if c == '\n':
          draw.fill(x=16*x, y=nsep+4+fonth*y, w=17, h=fonth, bg=0xffff)
        elif c == '\0':
          draw.set_color(0, bg=0xffff)
          draw.string(cmd[y], 16*x, nsep+4+fonth*y, width=3*16)
          draw.set_color(0xffff, bg=0)
        else:
          draw.string(c, 16*x, nsep+4+fonth*y, width=17)
    
  def drawLargeKbd(self, event1, clayout):
    draw = wasp.watch.drawable
    x = event1 // 16
      
    draw.fill()
    if clayout[0][-1] != '\0':
      x = min(max(x, 2), len(clayout[0]) - 3)
    else:
      x = min(max(x, 2), len(clayout[0]) - 2)
        
    self.mode = [clayout[0][x-2:x+3], clayout[1][x-2:x+3], clayout[2][x-2:x+3], clayout[3][x-2:x+3]]

    draw.set_font(fonts.sans24)

    for i in range(4):
      for j, c in enumerate(self.mode[i]):
        if c == '\n':
          draw.fill(x=48*j, y=48*i+40, w=48, h=32, bg=0xffff)
        elif c == '\0':
          draw.fill(x=48*j, y=48*i+40, w=96, h=32, bg=0xffff)
          draw.set_color(0, bg=0xffff)
          draw.string(cmd[i], 48*j+16, 48*i+48)
          draw.set_color(0xffff, bg=0)
        else:
          draw.string(self.mode[i][j], 48 * j, 48 * i + 48, width=48)

  def _draw(self):
    self.drawText(self.text, cursor=True)
    self.drawKbd()
      
  def foreground(self):
    wasp.system.request_event(wasp.EventMask.TOUCH | wasp.EventMask.SWIPE_UPDOWN | wasp.EventMask.SWIPE_LEFTRIGHT)
    self._draw()

  def print(self, *args, **kwargs):
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    self.output += output.getvalue()
    output.close()

  def touch(self, event):
    draw = wasp.watch.drawable
    
    if self.mode:
      x = event[1] // 48
      y = event[2] // 48 - 1
      x = min(x, len(self.mode[y]) - 1)

      if self.mode[y][x] == '\0':

        self.drawKbd()
        # print('DO', cmd[y])
        local = locals()
        local.update({'print': self.print})
        self.output = ''
        try:
          exec('\n'.join(self.text), globals(), local)
        except Exception as e:
          self.output += str(e)
        self.drawText(self.output.split('\n'))
      else:
        if self.mode[y][x] == '\n':
          self.text.insert(self.ychar + 1, self.text[self.ychar][self.xchar:])
          self.text[self.ychar] = self.text[self.ychar][:self.xchar]
          self.xchar = 0
          self.ychar += 1
        else:
          # insert plain char at current position
          self.text[self.ychar] = self.text[self.ychar][:self.xchar] + self.mode[y][x] + self.text[self.ychar][self.xchar:]
          self.xchar += 1
        self._draw()
      self.mode = None

    elif event[2] >= nsep:
      self.drawLargeKbd(event[1], layout[self.page])
    else:
      # the plan is to update the cursor here, but for now make sure the output is gone
      self._draw()

  def swipe(self, event):
    if self.mode:
      self._draw()
      self.mode = None
    else:
      if event[0] == wasp.EventType.UP:
        self.page = (self.page + 1) % len(layout)
        self.drawKbd()
      if event[0] == wasp.EventType.DOWN and event[2] >= nsep:
        self.drawLargeKbd(event[1], layout[(self.page + 1) % len(layout)])
      if event[0] == wasp.EventType.LEFT and event[2] >= nsep and len(self.text) > 0:
        # delete to left of cursor
        if self.xchar != 0:
          self.xchar -= 1
          self.text[self.ychar] = self.text[self.ychar][:self.xchar] + self.text[self.ychar][self.xchar+1:]
          self.drawText(self.text, cursor=True)
      if event[0] == wasp.EventType.RIGHT and event[2] >= nsep and len(self.text) > 0:
        # delete to right of cursor
        if self.xchar < len(self.text[self.ychar]):
          self.text[self.ychar] = self.text[self.ychar][:self.xchar] + self.text[self.ychar][self.xchar+1:]
          self.drawText(self.text, cursor=True)
      if event[0] == wasp.EventType.LEFT and event[2] < nsep:
        # move cursor left
        self.xchar -= 1
        if self.xchar == 0:
          if self.ychar != 0:
            self.ychar -= 1
            self.xchar = len(self.text[self.ychar])
          else:
            self.xchar = 1
        self.drawText(self.text, cursor=True)
      if event[0] == wasp.EventType.RIGHT and event[2] < nsep:
       # move cursor right        
        self.xchar += 1
        if self.xchar > len(self.text[self.ychar]):
          if self.ychar != len(self.text) - 1:
            self.ychar += 1
            self.xchar = 0
          else:
            self.xchar -= 1
        self.drawText(self.text, cursor=True)
