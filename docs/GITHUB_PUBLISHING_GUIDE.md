# GitHub Publishing Guide (macOS)

This guide is for first-time or early-stage GitHub users publishing this repo.

## 1. Open Terminal in repo root

```bash
cd ~/Desktop/Sentinel/Sentinel.1
```

## 2. Confirm `.env` is ignored

```bash
cat .gitignore | grep -E '^\.env$|^\.env\.\*$'
```

You should see `.env` ignore rules.

## 3. Initialize git (if needed)

```bash
git init
git branch -M main
```

If git is already initialized, skip this step.

## 4. Check what would be committed

```bash
git status
```

Before staging, verify:

- `.env` is not listed
- no local secret files are listed
- no large generated artifacts are listed

## 5. Stage files

```bash
git add .
```

Then verify again:

```bash
git status
```

## 6. Create first commit

```bash
git commit -m "Prepare Sentinel for public GitHub release"
```

## 7. Create repo on GitHub.com

1. Go to https://github.com/new
2. Choose repository name (example: `sentinel`)
3. Leave “Initialize with README” unchecked (repo already has files)
4. Create repository

## 8. Add remote and push

SSH:

```bash
git remote add origin git@github.com:<your-user-or-org>/<repo-name>.git
git push -u origin main
```

HTTPS:

```bash
git remote add origin https://github.com/<your-user-or-org>/<repo-name>.git
git push -u origin main
```

## 9. Verify what is public

After push:

1. Open the repository page on GitHub
2. Confirm `.env` is not present
3. Confirm docs/readme render correctly
4. Confirm only intended files are visible

## 10. Typical update workflow

```bash
git status
git add .
git commit -m "Short description of change"
git push
```

## 11. If `.env` was accidentally tracked

```bash
git rm --cached .env
git commit -m "Stop tracking .env"
git push
```

Then rotate any exposed secrets immediately.
