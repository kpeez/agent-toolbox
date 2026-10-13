# Source: Slack

Slack holds deliberation that never reached a ticket or a document. It matters
most when the PR and tracker record is thin.

## check-access

When a search call fails on authentication, stop. Record "Slack: not
searched, the Slack server needs authentication" as a gap, and return no
findings. Do not start the authentication flow from a lane; the user can
authenticate and run the lane again.

## author-window

Search messages from the PR author in the days around the merge date. This
narrows the search and often finds the discussion.

## pr-link

Search for the PR URL, or for `/pull/<number>`. Reviews and announcements
often link the PR.

## error-string

When the code handles a specific error, search for the error text. Incident
threads often appear.

## read-threads

Open the whole thread for each hit. A single message often reads differently
in its thread.

## Read with care

- Retention limits can delete old messages. When results stop at a date,
  record that date as a gap.
- Direct messages are often not searchable. Record that limit.
- Casual remarks are not decisions. Look for a considered discussion.
