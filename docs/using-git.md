# Git Overview

## Commands
A more exhaustive cheat sheet with explanations is available [here](https://www.atlassian.com/git/tutorials/atlassian-git-cheatsheet). The most commonly-used commands are:
- `git status`
- `git add <file>`
- `git commit -m <message>`
- `git push`
- `git pull`

## Examples
<details><summary>Downloading changes from GitHub</summary>

```sh
git pull --rebase
```
</details>

<details><summary>Committing all changes and uploading to GitHub</summary>

```sh
git add .                # Add all files in the current directory
git status               # Check that all the files you expected have been added
git commit -m <message>  # Include a concise explanation of the changes (typically under 50 characters)
git push                 # Upload to GitHub
```
</details>
