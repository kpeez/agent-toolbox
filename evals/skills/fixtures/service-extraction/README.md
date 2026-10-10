# Thumbnail service notes

The image API currently resizes files in-process. The proposed service boundary may reduce memory spikes,
but deployment, retry ownership, cache keys, and local development remain undecided. The team wants a
short plan to review before any code changes. There is no accepted architecture yet.
