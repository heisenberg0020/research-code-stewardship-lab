# Task 1 Report: Freeze Legacy Directories and Establish Package Red Light

## Frozen baseline

`tests/research_audit_training_v2/fixtures/legacy_tree.sha256` records SHA-256
hashes for the PDF, every non-cache source or documentation file in
`LLM4SBR_code_judgement_training`, and source, documentation, and requirements
files in `LLM4SBR-main`. It excludes data artifacts, `.xlsx` files, temporary
outputs, and cache files.

## Red-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: 4 tests ran; `test_protected_files_match_frozen_hashes` and
`test_student_files_do_not_reveal_answer_labels` passed. The two structural
tests failed because `LLM4SBR_research_audit_training_v2` did not exist:
`test_v2_tree_has_exactly_four_levels` reported the missing root, while the
per-level material test consequently reported the first missing `README.md`.
There were no import or syntax errors.

## Green-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: all 4 tests passed in 0.007s. An independent repeat of the
same command also passed. `cmp -s` confirmed that `FRAMEWORK_OVERVIEW.md` is
an exact copy of `docs/FOUR_LEVEL_RESEARCH_CODE_AUDIT_OVERVIEW.md`, and all
four `DO_NOT_OPEN_UNTIL_FINISHED` directories are empty.

## Created files

- `tests/__init__.py`
- `tests/research_audit_training_v2/__init__.py`
- `tests/research_audit_training_v2/helpers.py`
- `tests/research_audit_training_v2/fixtures/legacy_tree.sha256`
- `tests/research_audit_training_v2/test_00_package_contract.py`
- `LLM4SBR_research_audit_training_v2/README.md`
- `LLM4SBR_research_audit_training_v2/FRAMEWORK_OVERVIEW.md`
- `LLM4SBR_research_audit_training_v2/PROGRESSION.md`
- Four level directories, each with `README.md`, `ANSWER_SHEET.md`, and an
  empty `DO_NOT_OPEN_UNTIL_FINISHED` directory.

## Self-review conclusion

Only the v2 package, its tests and fixture, and the Task 1 progress/report
records were added or updated. The protected-file test passes against the
frozen baseline, the public-file disclosure check passes, and the v2 package
contains exactly the required four levels. No legacy training package, original
source tree, or PDF file was edited.

## Review-finding repair: manifest coverage and Chinese leakage detection

### Fresh red-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: 6 tests ran and exactly 2 failed. The focused leakage test
failed because the prior raw pattern treated `\\s` as a literal backslash plus
`s`, so it did not match `正确候选：A` (and therefore did not reach `答案：A`).
The manifest-coverage test failed because the derived protected set contained
17 paths absent from the fixture: the non-cache `.DS_Store` in the old training
package; source, documentation, and `.txt` files under `LLM4SBR-main/Data`; and
documentation under `LLM4SBR-main/Search_data`. The other 4 tests passed.

### Green-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: all 6 tests passed in 0.024s. The manifest test now derives the
set from every non-cache ordinary file in the old training package, and from
every recursive `.py`, `.md`, `.txt`, `.ipynb`, or requirements file in the
original source tree while excluding caches and `tmp`; it also includes the
PDF. The public-file scan now reuses the tested `LEAK_PATTERN` constant with
the corrected raw `\s` whitespace expression.

### Exact files changed for this repair

- `tests/research_audit_training_v2/test_00_package_contract.py`
- `tests/research_audit_training_v2/fixtures/legacy_tree.sha256`
- `.superpowers/sdd/task-1-report.md`

No protected file was modified.

## Review-finding repair: exclude metadata and data artifacts

### Fresh red-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: 7 tests ran; exactly
`test_manifest_excludes_metadata_and_data_artifacts` failed because the
manifest contained `LLM4SBR_code_judgement_training/.DS_Store`. The remaining
6 tests passed, including the then-current manifest-set test, establishing that
the failure was caused by the new exclusion requirement rather than an import,
syntax, or hash failure.

### Green-light verification

Command run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Output summary: all 7 tests passed in 0.012s. The derived protected set now
excludes dot metadata from the old exercise package; it includes only `.py`,
`.md`, and `.ipynb` source/documentation extensions from the original source
tree, plus files whose name begins with `requirements`. It excludes the six
`Data/**/{train,test,all_train_seq}.txt` artifacts. The fixture removed those
six entries and the `.DS_Store` entry; source and documentation files in
`Data` and `Search_data` remain frozen.

### Exact files changed for this repair

- `tests/research_audit_training_v2/test_00_package_contract.py`
- `tests/research_audit_training_v2/fixtures/legacy_tree.sha256`
- `.superpowers/sdd/task-1-report.md`

No protected file was modified.
