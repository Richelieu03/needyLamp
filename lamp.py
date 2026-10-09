"""Placeholder stub: C will overwrite this file directly."""
import time

_on = False


def set_light(on: bool):
    global _on
    if on != _on:
        _on = on
        print("lamp:", "on" if on else "off")


def run():
    while True:
        time.sleep(1)
