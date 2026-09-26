validate_session never expires old sessions: the expiry comparison inside
SessionManager is wrong, so stale sessions stay valid forever.
