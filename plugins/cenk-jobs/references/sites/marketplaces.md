# Talent marketplaces: site notes

Read by the search session for a posting from a talent marketplace (Toptal, Lemon.io, Arc, Turing, Andela and the
like), by the plan session for its row, and by a session that applies to one.

- Draft: no draft known; each marketplace has its own sign-up and vetting.
- A marketplace's posting on a job board advertises its talent pool, not one role: its title and must-haves are the
  pool's (example: "Senior Golang Engineer"), and the role the person gets comes from the vetting.
- When the vetting names the role, record it on the row: `track.py role <id> "<the role>"` (the title becomes the
  role; the posting's title and stored fit move into the row's history; the status stays). Example: `track.py role
  P1a2b3c4d "Backend developer, Java + Kafka"`.
- Until then `track.py regrade` holds the row when the person is working on it (an open to-do, a hiring step): it is
  never skipped by the pool's must-haves; the plan skill asks the person about it.
- Two postings of one marketplace are often one process: the vetting runs through the row sent first. Record its
  steps on that row (`track.py step`); a second row needs no second sign-up.
