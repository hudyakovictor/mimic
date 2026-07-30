# ML governance

A model version is deployable only with: artifact checksum, code commit, training dataset manifest, feature schema, evaluation report, calibration profile, intended use, known limitations and approver.

Promotion flow: `DRAFT → VALIDATED → SHADOW → ACTIVE → RETIRED`. Rollback switches the active pointer; historical decisions remain bound to their original version.

Baselines are curated from verified genuine sessions. Reviewer verdicts enter a quarantine dataset and never retrain automatically. Evaluation splits by person, session and capture device. Accuracy alone is prohibited; report false acceptance/rejection and confidence intervals.
