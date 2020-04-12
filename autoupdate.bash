curr_branch="$(git rev-parse --abbrev-ref HEAD)"
echo "On branch $curr_branch"
git checkout gh-pages
python src/case_tracker.py --use-web-data --create-data-table
git add -A .
git commit -m "Auto update with new data"
git push
git checkout "$curr_branch"
echo "On branch $curr_branch"
curr_branch="$(git rev-parse --abbrev-ref HEAD)" &&
	git checkout gh-pages &&
	python src/case_tracker.py --use-web-data --create-data-table &&
	asciidoctor -b html5 -o index.html README.asciidoc &&
	git add -A . &&
	git commit -m "Auto update with new data" &&
	git push &&
	git checkout "$curr_branch" &&
	echo "Back on branch $curr_branch"
