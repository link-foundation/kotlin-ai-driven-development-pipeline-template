# Changesets

Add a new Markdown file for production build or source changes. Begin it with
a three-line header containing `bump: patch`, `bump: minor`, or `bump: major`,
then write a release note. Use a unique filename per change. The release job
applies the highest pending bump and consumes all pending files in one commit.
