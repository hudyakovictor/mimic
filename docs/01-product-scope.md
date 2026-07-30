# Product scope

## Product decision
The system does not promise universal mask detection. It detects **inconsistency between a claimed person's verified facial-motion baseline and a new landmark sequence**, and exposes the evidence to a reviewer.

## Primary user journeys
1. Operator registers an uploaded video and claimed subject.
2. System extracts one stable face track and evaluates data quality.
3. Accepted motion is normalized and compared with verified baselines.
4. Reviewer sees a risk score, quality, anomalies and time ranges.
5. Reviewer records a verdict; the original model decision remains immutable.

## v1 must-have
- explicit job lifecycle and retries;
- quality rejection rather than forced decisions;
- versioned landmark/feature schemas;
- subject baseline isolation;
- evidence with time ranges;
- RBAC and append-only audit;
- React queue, decision and review workflow;
- model/version registry.

## Non-goals
- emotion or intent detection;
- identification of unknown people;
- covert surveillance;
- texture/depth/rPPG analysis;
- automatic training from reviewer actions;
- a single confidence value without quality/evidence.

## Success metrics
- 95% of accepted jobs complete inside five minutes for a ten-minute video;
- zero silent fallback to an unversioned model;
- every decision reproducible from asset hash, feature version and model checksum;
- reviewers can complete a decision in under two minutes;
- quality gate false acceptance tracked separately from model performance.
