# Deploying the site

You do every step below yourself. Nothing here was run for you: no commit, no push, no settings change.

The live address will be `https://vavme.github.io/credit-model-stress-testing/`. The base path `/credit-model-stress-testing/` is one value in `site/config.json`.

## How the build works

1. **Stage 1, on your machine only:** `python -m poetry run python site/build_data.py` reads the train split and writes the aggregated JSON in `site/data/`. These files are committed. The raw data never leaves your machine.
2. **Stage 2, on your machine and in GitHub Actions:** `python site/build_site.py` renders the pages into `site/dist/` and runs all checks. It uses only the Python standard library.

GitHub Actions runs stage 2 only. If any check fails, the job fails and nothing is published.

## Before you push: check locally

```bash
python site/build_site.py
python site/serve.py
```

Both need only Python 3.11 and no installed packages. To run the tests too, use whichever Poetry command works on your machine: `poetry run pytest`, or `python -m poetry run pytest`, or `py -m poetry run pytest`. If your `python` says "No module named poetry", Poetry is installed for another Python, so try the other two forms. The site build does not depend on it.

Open `http://localhost:8765/credit-model-stress-testing/` and look at all five pages. Press Ctrl+C to stop the preview.

If you changed anything in `reports/eda/`, run `python -m poetry run python site/build_data.py` first, then check the new numbers on the page.

## Step 1: choose what to commit

```bash
git status
```

You should see these new or changed items:

| Item | Commit it? |
|---|---|
| `site/` (without `site/dist/`, which is ignored) | Yes |
| `.github/workflows/pages.yml` | Yes |
| `tests/test_site_build.py`, `tests/test_site_checks.py` | Yes |
| `.gitignore` (adds `site/dist/`) | Yes |
| `.claude/launch.json` | Your choice. It only configures the desktop app preview. Add `.claude/` to `.gitignore` if you do not want it public. |

`docs/site_*.md` is gitignored and stays on your machine.

## Step 2: check the repository is safe to make public

- [ ] `git status` shows nothing under `data/` and no `.csv` file inside `site/`.
- [ ] You checked Kaggle's competition rules about showing aggregated statistics and column descriptions. (You said you did. The site shows the descriptions from the Kaggle file. You can switch to your own text with `"description_source": "own"` in `site/config.json` and fill `site/content/own_descriptions.json`, which the build creates on first use.)
- [ ] The footer shows the name and links you want (`site/config.json`).
- [ ] The old `example_values` column is still in the history of commit 152abf0. You said you will handle that in November.

## Step 3: commit and push

```bash
git add site .github tests/test_site_build.py tests/test_site_checks.py .gitignore
git commit -m "Add EDA story site and Pages workflow"
git push origin main
```

(Use your own commit message and attribution lines as you prefer.)

## Step 4: turn on GitHub Pages (one time)

1. Open `https://github.com/vavme/credit-model-stress-testing/settings/pages`.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Do not pick a branch. The workflow publishes the site.

Do this before or right after the first push. If you push first, the first run may fail at the "configure pages" step. Open the **Actions** tab, then **Deploy site to GitHub Pages**, then **Re-run all jobs**.

## Step 5: watch the first run and check the live site

1. Open the **Actions** tab. The run "Deploy site to GitHub Pages" has two jobs, `build` and `deploy`. Both should turn green in about a minute.
2. If `build` fails, open it. The log lists each failed check in plain words, for example a number that is not in the facts file.
3. Open `https://vavme.github.io/credit-model-stress-testing/` and check:
   - [ ] The home page loads and the charts appear.
   - [ ] The footer shows your name and the GitHub link.
   - [ ] `.../explorer.html?feature=EXT_SOURCE_3` opens a column.
   - [ ] The "AI-generated draft, not yet adopted by the author" label shows in sections 7 and 8.
   - [ ] The pages work on your phone.
4. Optional score check on the live site: `npx lighthouse https://vavme.github.io/credit-model-stress-testing/ --preset=desktop --view`

## Updating the site later

| Change | What to do |
|---|---|
| New or changed EDA numbers | Run `site/build_data.py`, commit `site/data/`, push. |
| Text on a page | Edit the file in `site/src/`, run `python site/build_site.py`, commit, push. |
| You adopt the shortlist and predictions | Set `"ai_draft_adopted": true` in `site/config.json`. This changes the label to "Adopted by the author". To use your own wording, edit the reasons in `src/data/shortlist.py` and the candidate text in `build_candidates` in `site/build_data.py`, then run `build_data.py` again. |
| Switch to your own column descriptions | Set `"description_source": "own"` and fill `site/content/own_descriptions.json`. |
| Roll back | Revert the commit and push. The workflow publishes the old version. |

## Alternative: Cloudflare Pages

Use this if you prefer it to GitHub Pages. You create the Cloudflare account and project yourself.

Cloudflare serves the site from the root of its own address, so the base path must be `/` for that build. The build reads it from an environment variable, so you do not edit any file.

1. In the Cloudflare dashboard, go to **Workers and Pages**, then **Create**, then **Pages**, then **Connect to Git**, and choose this repository.
2. Build settings:
   - Framework preset: **None**
   - Build command: `python3 site/build_site.py`
   - Build output directory: `site/dist`
3. Environment variables (production):
   - `SITE_BASE_PATH` = `/`
   - `PYTHON_VERSION` = `3.11`
4. Save and deploy. The site appears at `https://<project-name>.pages.dev/`.

To test the root build on your machine: PowerShell `$env:SITE_BASE_PATH="/"; python site/serve.py`. In Git Bash, run `MSYS_NO_PATHCONV=1 SITE_BASE_PATH=/ python site/serve.py`, because Git Bash otherwise rewrites the `/`.

If you use Cloudflare, you can turn off the GitHub workflow by deleting `.github/workflows/pages.yml`, or leave both.

## What the checks do

`site/checks.py` runs inside every build:

- no raw-data file types, and no column or key named like an example, a sample or an ID;
- no array that looks like row-level data, and size limits (site under 15 MB, data under 5 MB);
- no em dash or en dash anywhere;
- every number in the page text exists in `site/data/facts.json`;
- every internal link and anchor resolves under the base path.

## Known limits

- The shortlist, the corruption candidates and their predictions are AI drafts. The site says so at the top of each block until you set `ai_draft_adopted`.
- Charts need JavaScript. Each chart has a text summary and a table that work without it.
- Scores were measured with headless Chrome. Please also open the live site on a real phone.
