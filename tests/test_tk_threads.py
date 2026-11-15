"""Tk objects freed on another thread are finished off on Tk's own thread (ui/tk_threads.py)."""

import gc
import threading
import tkinter as tk

from ui import tk_threads


def test_a_variable_dropped_on_another_thread_is_unset_on_tks_thread(tk_root):
    tk_threads.wrap_classes()
    tk_threads.drain()
    var = tk.StringVar(tk_root, value="hello")
    name = str(var)
    box = [var]
    del var
    assert tk_root.tk.call("info", "exists", name)

    def drop():
        box.clear()                     # the last reference goes away here, off Tk's thread
        gc.collect()

    t = threading.Thread(target=drop)
    t.start()
    t.join(5)
    assert not t.is_alive()
    assert tk_threads.pending() >= 1
    assert tk_root.tk.call("info", "exists", name)       # not touched from the other thread
    assert tk_threads.drain() >= 1
    assert not tk_root.tk.call("info", "exists", name)


def test_on_tks_own_thread_nothing_changes(tk_root):
    tk_threads.wrap_classes()
    tk_threads.drain()
    image = tk.PhotoImage(master=tk_root, width=4, height=4)
    name = image.name
    del image
    assert name not in tk_root.tk.call("image", "names")
    assert tk_threads.pending() == 0
