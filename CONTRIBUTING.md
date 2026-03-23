# Contributing to SimStock

We welcome and encourage contributions to SimStock, such as bug reporting, feature suggestions, documentation improvements, and submitting code changes. 

Developers wishing to contribute should follow the steps below.

## Development setup
1. Clone the repo
2. Install dependencies via either:
```bash
poetry install
```
or 
```bash
conda env create -f environment.yaml
conda activate simstock
pip install -e .
```
> **_NOTE:_**  You will also need a local copy of EnergyPlus 8.9 to run this version of SimStock.
3. Run tests:
```bash
poetry run python -m unittest -v
```
or if installed with conda:
```bash
python -m unittest -v
```

## Bug reporting
To report a bug, in the first instance please open a GitHub issue and include:
- What incorrect behaviour you observed and ideally what you expected should have happened.
- Steps to reproduce the bug, including SimStock and Python versions as well as your operating system.

## Code and feature contributions
To contribute new code and features, please follow the standard pull request process:
1. Create a new branch from `main`.
2. Implement your changes. Try and keep them small.
3. Update or add tests for any new behaviour.
4. Ensure tests pass.
5. Open a pull request and ensure it includes a summary of the changes, the purpose of the changes, and any links to appropriate open issues.
