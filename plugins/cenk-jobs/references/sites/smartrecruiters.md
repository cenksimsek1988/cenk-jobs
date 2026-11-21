# SmartRecruiters: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- Draft: no draft known.
- The form sits in a shadow DOM: never move, unhide or rebuild a hidden input to fill it. Upload a file through
  the page's own upload button and its dialog; a script cannot reach the CV file input.
- Salary and availability are comboboxes: type the value, then click one of its options; a typed value alone is
  not kept. A text field refuses ";": write "," instead.
- A later page can hold required items the record does not answer: stop there and return needs-person with each
  item, word for word.
