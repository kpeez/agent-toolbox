# Handoff

Goal: wait_for_item in poller.py must return an item that arrives exactly at the timeout boundary.

Done so far:
- Read poller.py and the failing case. The loop stops when the elapsed time reaches the timeout, before it checks the queue one last time.
- Wrote no code yet.

Left to do:
- Change the loop so the last check happens at the boundary.
- Run python3 -m unittest.
- Leave the other wait rules alone.
