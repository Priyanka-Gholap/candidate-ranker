# Candidate Ranking Engine

This repository contains the code and methodology for the **India Runs by Redrob AI** hackathon (Track 1).

The engine is designed to rank a dataset of candidate profiles to identify the top 100 fits for the Senior AI Engineer role.

## Architecture

The system evaluates candidates through a multi-stage scoring pipeline:

1. **Honeypot Filtering**: Identifies and excludes profiles with illogical timelines, inconsistent job durations, or invalid skill proficiencies.
2. **Location Criteria**: Evaluates candidate locations, prioritizing candidates in Tier-1 cities or open to relocation.
3. **Multi-Criteria Scoring**:
   * **Role Relevance (35%)**: Evaluates professional titles and prioritizes hands-on experience in product environments over consulting/IT services.
   * **Skill Depth (30%)**: Matches core machine learning and search skills, factoring in duration and proficiency.
   * **Experience Alignment (20%)**: Focuses on the target range of 5–9 years.
   * **Engagement Signals (15%)**: Incorporates responsiveness, notice periods, and recent activity.
4. **Deterministic Sorting**: Ranks candidates based on score, with alphabetical candidate ID tie-breaking.
5. **Reasoning Generation**: Generates brief factual explanations for the final output.

## Reproducing the Shortlist

### Prerequisites
* Python 3.8+ (No external dependencies required).

### Execution Command
Run the following command to rank candidates and write the output CSV:

```bash
python rank.py --candidates ./candidates.jsonl --out ./datasets.csv
```

The output file `datasets.csv` will contain exactly 100 candidates ranked by relevance.
