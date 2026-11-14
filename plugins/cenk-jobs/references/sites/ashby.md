# Ashby: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- The form's questions, before opening Chrome: a POST to `https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting`
  (Python; WebFetch only gets), variables `organizationHostedJobsPageName` and `jobPostingId`: `applicationForm`
  sections, each field in `fieldEntries` with `isRequired`.
- Ashby keeps no draft: a form with an essay question waits until the person's answer is in the records.
- A React field takes the native value setter, then `input` and `change` events; Yes/No answers are buttons over
  hidden checkboxes; a radio or checkbox is set by clicking its label. The public posting API answers 403 without a
  browser User-Agent.
