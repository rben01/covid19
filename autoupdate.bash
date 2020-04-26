#!/usr/bin/env bash
ghpages_branch='master'

curr_branch="$(git rev-parse --abbrev-ref HEAD)" &&
	git checkout "$ghpages_branch" &&
	python src/case_tracker.py --use-web-data --create-data-table --force-graphs --force-interactive &&
	touch README.asciidoc &&
	asciidoctor --base-dir docs -o index.html README.asciidoc &&
	git status &&
	git add -A . &&
	git commit -m "Auto update with new data" &&
	git checkout "$curr_branch" &&
	if [ "$curr_branch" != "$ghpages_branch" ]; then echo "Back on branch '$curr_branch'"; else echo "Still on branch '$ghpages_branch'"; fi
