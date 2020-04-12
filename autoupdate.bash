curr_branch="$(git rev-parse --abbrev-ref HEAD)"
echo "On branch $curr_branch"
git checkout gh-pages
python src/case_tracker.py --use-web-data --create-data-table
git add -A .
git commit -m "Auto update with new data"
git push
git checkout "$curr_branch"
echo "On branch $curr_branch"
