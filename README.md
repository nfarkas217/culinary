# culinary

## Conda environment

To activate this environment:
$ conda activate culinary

To deactivate an active environment:
$ conda deactivate

## Git branching

create new branch wth changes:
git checkout main
git pull origin main
git checkout -b feature/strict-soup

push to working branch:
git add .
git commit -m "Add strict soup validation logic"
git push --set-upstream origin feature/strict-soup

merge back to main branch:
git checkout main
git pull origin main
git merge feature/strict-soup
git push origin main

delete feature branch:
git branch -d feature/strict-soup
git push origin --delete feature/strict-soup
