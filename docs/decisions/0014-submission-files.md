# 0014: Files in submissions: code as text, own files per item, generated alt text

- Status: accepted
- Date: 2026-11-19

## Context

ADR 0009 lists "code files" among the private submission files, and
CLAUDE.md requires an alt text field for every image. Implementing the
requirement types (#23, #24) raised three questions:

- Uploaded code is shown with syntax highlighting; keeping the uploaded
  file as well would mean a second, raw copy that needs its own download
  route and access checks.
- Photos and files stay in a draft until removed, and a resubmission
  starts from the previous submission's content. Sharing a stored file
  between two items would make deleting one item break the other.
- Participants are children aged 7 to 16 who upload several photos from a
  phone. A required alt text per photo would slow every upload down, and
  most entries would be meaningless ("Foto", "asdf").

## Decision

1. **Code uploads are stored as text.** A code file (UTF-8 text, at most
   200 KB) is read into `SubmissionItem.text`; its original name is kept
   for display and highlighting. No file is stored, so there is nothing to
   serve.
2. **Every item owns its files.** When a resubmission keeps a photo or
   file of the previous submission, the file is copied under a new random
   name. File deletion happens only after the transaction commits.
3. **Participant photos get a generated alt text** ("Foto: <label of the
   requirement> (<n>)") instead of an alt text field. The rule "every
   image has an alt text field, required when an image is set" stays in
   force for images that coaches add (task instructions, later content
   images).

## Consequences

- Code needs no private file kind; highlighting works on the stored text.
  The exact bytes of an uploaded code file (e.g. its encoding) are not
  kept.
- Copies cost storage for photos kept across resubmissions. Accepted: the
  reviewed submission stays exactly as reviewed, and deletion stays simple.
- Screen reader users hear which requirement and which number a photo
  belongs to, not what it shows. Coaches reviewing photos see them anyway;
  if participants should describe their photos later, an optional field
  can be added without changing this decision for coaches' images.
