In-memory cache for rendered map tiles used by the preview service.

Run the replay benchmark against a fixed seed with:

    python3 measure.py --seed N

The hit rate moves a little from seed to seed. With the FIFO cache in
`cache.py`, the mean hit rate across seeds 1 to 5 is 0.668.
