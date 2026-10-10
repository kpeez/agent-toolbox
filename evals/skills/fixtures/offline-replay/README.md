# Event replay

A replay tool will rebuild local projections from archived events. The first release must be read-only,
resume after interruption, and avoid changing current live projections. The archive contains duplicate
event IDs and malformed records. The current parser and projection code are separate modules.

The work spans a parser, cursor persistence, and an operator command. A new session will implement it.
