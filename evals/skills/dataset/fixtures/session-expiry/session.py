def valid(session, now):
    return session["expires_at"] >= now
