# LLM4SBR Research Audit Training v2

This package contains a four-level training progression for auditing research code.

Passing public checks establishes only the package contract. It does not establish
that an implementation, experiment, or scientific conclusion is correct.

Run all learner-visible checks with:

```bash
python run_all_public_checks.py
```

Use `verify_package.py` for the public structural verification. Instructor-only
answers and probes remain isolated inside each level and are never imported by
the public verifier.
