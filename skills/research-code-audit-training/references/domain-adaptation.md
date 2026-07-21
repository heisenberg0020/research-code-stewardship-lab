# Domain adaptation

Map generic terms to the paper's actual independent units before creating faults.

| Generic term | Possible domain equivalents |
|---|---|
| Raw entity | user/session, patient, subject, document, graph, environment, trajectory, time block |
| Prefix/window | crop, patch, subsequence, visit window, temporal slice, augmentation |
| Candidate set | labels, retrieval corpus, action space, negatives, controls |
| Checkpoint | policy snapshot, fitted estimator, prompt, index, selected pipeline |
| Protected test | held-out cohort, future period, benchmark server, untouched environment seeds |

For medical or human-subject work, never copy sensitive records into the exercise; construct synthetic fixtures preserving only the relevant invariants. For temporal, graph, and reinforcement-learning papers, freeze chronology, component/subject boundaries, environment version, termination semantics, and interaction-data reuse rules.

Do not force recommendation-specific metrics or session logic onto another domain. Preserve the four contract levels while adapting schemas and probes to the paper's scientific unit.
