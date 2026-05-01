# Anonymous Mirror Procedure (anonymous.4open.science)

This document records how to produce the **anonymised release URL** that
appears in `paper/main.tex` for the camera-ready version. anonymous.4open.science
is a free service that mirrors a public GitHub repository as an
anonymous URL, stripping git history, author information, and email
addresses from view.

## Prerequisites

1. **GitHub repository must be public.** anonymous.4open.science does not
   support private repositories (only access via reviewers is supported via
   the public URL).
2. **No identity leakage in repository contents.** The current repository
   has been audited:
   - Author block in `paper/main.tex` is `Anonymous Authors`.
   - Dataset files in `dataset_release/` carry no annotator names
     (verified via grep).
   - HuggingFace dataset URL placeholder in `paper/main.tex` is
     `[anonymised release URL to be added]`.
   - Recovery / incident notes (`RECOVERY_STATUS.md`) are gitignored.
3. **Git history is acceptable as visible.** anonymous.4open.science
   strips author email and name from commits in the mirror, but the
   commit messages themselves are visible. Audit `git log` before
   submission.

## Submission flow

1. Open https://anonymous.4open.science/ in a browser.
2. Click **Submit**.
3. Paste the GitHub URL: `https://github.com/eliashossain001/nanobubbleeval`
4. Choose **branch: main**.
5. Set the **anonymisation level** to *strict* (default).
6. Submit. The service generates an anonymous URL of the form:
   ```
   https://anonymous.4open.science/r/nanobubbleeval-XXXX
   ```
7. **Verify the anonymous URL** by opening it in a fresh browser session
   (or incognito): no author name, no email, no identifying URL fragments.

## After the URL is generated

Replace the two placeholders in `paper/main.tex` §6:

```diff
- \texttt{[anonymised release URL to be added]}
+ \texttt{https://anonymous.4open.science/r/nanobubbleeval-XXXX}
```

(both for the code link and the dataset link; both share the anonymous
mirror URL since the dataset is committed to `dataset_release/` in the
GitHub repo).

Replace the same placeholder in `metadata/croissant.json` and
`dataset_release/README.md`.

## Important caveats

- **anonymous.4open.science URLs expire** after the conference review
  cycle. Replace with the real GitHub / HuggingFace URLs in the
  camera-ready version.
- **Do NOT push the dataset_release/ directory to a public GitHub
  account that uses your real name in any commit before the abstract
  deadline.** The current repository is at `eliashossain001/...` —
  for double-blind review, the *anonymous mirror* is what reviewers see;
  the GitHub URL is not in the paper.
- The HuggingFace dataset at `EliasHossain/nanobubbleeval` is
  **private** and is the second-tier release path. Reviewers do not
  need it; they can use anonymous.4open.science for everything.

## Camera-ready transition

For the camera-ready version (after acceptance):

1. Make the GitHub repository fully public.
2. Make the HuggingFace dataset public (unless you choose to keep it
   private and host only via GitHub).
3. Replace the anonymous URL in `paper/main.tex` and
   `dataset_release/README.md` with the real URLs.
4. Update `metadata/croissant.json` `url` field with the real URL.
5. Add the BibTeX citation to `dataset_release/README.md`.
