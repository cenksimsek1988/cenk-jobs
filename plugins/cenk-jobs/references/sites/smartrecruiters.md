# SmartRecruiters: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- The form sits in a shadow DOM: never move, unhide or rebuild a hidden input to fill it. Upload a file through
  the page's own upload button and its dialog.
- A later page can hold required items the record does not answer: stop there and return needs-person with each
  item, word for word.
