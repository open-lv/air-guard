from machine import Signal

class LEDSignal(Signal):

  def ieslegt(self):
    self.value(1)
  def izslegt(self):
    self.value(0)

def pagaidit(v):
  sleep(v)