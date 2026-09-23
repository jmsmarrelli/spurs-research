"""Create and execute the three review notebooks with the current Python environment."""

import os, sys, json
import nbformat as nb
from nbclient import NotebookClient
from .common import ROOT


def run():
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    for key, folder in [
        ("JUPYTER_RUNTIME_DIR", "runtime"),
        ("IPYTHONDIR", "ipython"),
        ("MPLCONFIGDIR", "matplotlib"),
    ]:
        p = cache / folder
        p.mkdir(exist_ok=True)
        os.environ[key] = str(p)
    spec = cache / "jupyter/kernels/research"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [
                    sys.executable,
                    "-m",
                    "ipykernel_launcher",
                    "-f",
                    "{connection_file}",
                ],
                "display_name": "Python 3",
                "language": "python",
            }
        )
    )
    os.environ["JUPYTER_PATH"] = str(cache / "jupyter")
    jobs = [
        (
            "01_wembanyama_rim_footprint",
            "rim_footprint",
            "rim_estimates",
            "rim_raw",
            "rim_adjusted",
        ),
        (
            "02_three_guards_eight_groups",
            "guard_groups",
            "guard_groups",
            "guard_exposure",
            "guard_rim_intervals",
        ),
        (
            "03_wembanyama_playoff_shot_diet",
            "playoff_diet",
            "playoff_decomposition",
            "playoff_profile",
            "playoff_components",
        ),
    ]
    for stem, module, table, fig1, fig2 in jobs:
        article = (ROOT / f"reports/{stem}.md").read_text()
        book = nb.v4.new_notebook(
            metadata={
                "kernelspec": {
                    "name": "python3",
                    "display_name": "Python 3",
                    "language": "python",
                },
                "language_info": {"name": "python", "version": "3.12"},
            }
        )
        book.cells = [
            nb.v4.new_markdown_cell(article.split("##")[0]),
            nb.v4.new_code_cell(
                "from pathlib import Path\nimport os, sys\nroot = Path.cwd()\nif root.name == 'notebooks':\n    root = root.parent\nsys.path.insert(0, str(root))\nos.chdir(root)\nimport pandas as pd\nfrom IPython.display import display, Image\nfrom src import "
                + module
                + "\nsummary = "
                + module
                + ".run()\nfrom src import figures\nfigures.run()\nsummary"
            ),
            nb.v4.new_markdown_cell(
                "## Results\nThe following table is regenerated from the pinned inputs."
            ),
            nb.v4.new_code_cell(f"pd.read_csv('results/{table}.csv')"),
            nb.v4.new_code_cell(
                f"display(Image(filename='figures/{fig1}.png'))\ndisplay(Image(filename='figures/{fig2}.png'))"
            ),
        ]
        if module == "rim_footprint":
            code = "import json\ndisplay(json.loads(Path('results/lineup_summary.json').read_text()))\ndisplay(pd.read_csv('results/rim_sensitivity.csv'))\ndisplay(pd.read_csv('results/source_disagreements.csv'))"
            explanation = "## Audit and sensitivity\nInspect excluded periods, feed disagreements and the narrower score/clock sample before interpreting the coefficient."
        elif module == "guard_groups":
            code = "import json\ndisplay(json.loads(Path('results/guard_validation.json').read_text()))\ndisplay(pd.read_csv('results/guard_wemby_splits.csv'))\ndisplay(pd.read_csv('results/guard_review_queue.csv').head(9))"
            explanation = "## Forecast check and review queue\nThe chronological test predicts rim location. The event queue locates examples; it is not completed film coding."
        else:
            code = "from src.playoff_diet import weighted_profile, decomposition\nd = pd.read_csv('data/playoff_shots.csv.gz')\nr = d[d.phase.eq('Matched regular season')]\np = d[d.phase.eq('Playoffs')]\nweights = p.opponent.value_counts(normalize=True).sort_index()\na, b = weighted_profile(r, weights), weighted_profile(p, weights)\nparts = decomposition(a, b)\nassert abs(parts[0] + parts[1] - parts[2]) < 1e-12\ndisplay(pd.Series(parts * 100, index=['Location mix', 'Within-zone conversion', 'Total']))\ndisplay(pd.read_csv('results/playoff_opponents.csv'))\ndisplay(pd.read_csv('results/wemby_regular_trend.csv'))"
            explanation = "## Verify the accounting\nRecalculate the decomposition from matched shots, then inspect the opponent sample sizes and full-season context."
        book.cells += [nb.v4.new_markdown_cell(explanation), nb.v4.new_code_cell(code)]
        book.cells += [
            nb.v4.new_markdown_cell(
                "## Interpretation and limits\nRead the complete accompanying article for denominators, uncertainty, model selection, and the basketball decisions this analysis cannot identify. The results here are historical research, not a claim of team deployment."
            )
        ]
        path = ROOT / f"notebooks/{stem}.ipynb"
        NotebookClient(
            book,
            timeout=600,
            kernel_name="research",
            resources={"metadata": {"path": str(ROOT)}},
        ).execute()
        for cell in book.cells:
            cell.metadata.pop("execution", None)
        nb.write(book, path)
        print(path.name, "executed", flush=True)


if __name__ == "__main__":
    run()
