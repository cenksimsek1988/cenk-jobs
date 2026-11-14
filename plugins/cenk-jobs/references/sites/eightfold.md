# Eightfold and button dropdowns: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- A dropdown built from `input[type=button]` keeps the choice in its `value` while its label still reads "Select
  one": read the value, not the label. Eightfold careers sites ignore a plain click on a dropdown option: dispatch
  pointerdown, mousedown, pointerup, mouseup and click on the option element, in that order (`javascript_tool`).
