"""Bounded read-only I/O workers with completion polled exclusively by Tk."""
from concurrent.futures import ThreadPoolExecutor

_READERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="BusinessRead")


def run_background(owner, work, on_result, on_error=None):
    future = _READERS.submit(work)
    def poll():
        if not owner.winfo_exists():
            future.cancel()
            return
        if not future.done():
            owner.after(100, poll)
            return
        try:
            result = future.result()
        except Exception as exc:
            if on_error:
                on_error(exc)
            else:
                from tkinter import messagebox
                messagebox.showwarning("读取失败", str(exc), parent=owner)
        else:
            on_result(result)
    owner.after(100, poll)
    return future
