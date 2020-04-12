curr_branch="$(git rev-parse --abbrev-ref HEAD)"
git checkout gh-pages
git add -A .
git commit -m "Auto update with new data"
git push
git checkout "$curr_branch"
