# SuccessFactors: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- A SuccessFactors apply link (`talentcommunity/apply/<id>`) opens the site's home page when signed out: not a closed
  posting; open the job's own page. Signing in there from a job's Apply link can submit at once by quick apply from
  the stored profile, with no CV or answers: upload the CV to the profile first, or sign in from the site's home page,
  then apply.
- SuccessFactors behind a Career Site Builder front end: after sign-in, the Apply link lands on the portal's home
  page. Open the job by its requisition id inside the signed-in portal (example: search its jobs for `12345`).
- The visible "Upload a CV" label does nothing; click the `span.addAttachments` icon with `javascript_tool`, and its in-page
  dialog holds `input[type=file]` (name `fileData1`) for `file_upload`. Start the next upload only after the last one
  has finished.
