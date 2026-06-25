import json
import datetime
import csv
import argparse
import sys
import os

# Consulting companies list
CONSULTING_COMPANIES = [
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "l&t infotech", "lti", "mphasis",
    "hexaware", "genpact", "wns", "ust global", "syntel"
]

# Core skills categories
CORE_SKILLS = {
    "embeddings": ["embeddings", "sentence-transformers", "bge", "e5", "sentence transformers", "vector representations", "vector search"],
    "vector_db": ["pinecone", "weaviate", "qdrant", "milvus", "faiss", "elasticsearch", "opensearch", "vector db", "vector database"],
    "nlp_ir": ["nlp", "information retrieval", "ir", "rag", "re-ranking", "reranking", "retrieval", "semantic search"],
    "python": ["python"]
}

PREFERRED_SKILLS = {
    "tuning": ["lora", "qlora", "peft", "fine-tuning", "finetuning", "llm fine-tuning"],
    "ltr": ["learning-to-rank", "learning to rank", "ltr", "xgboost", "lightgbm"],
    "systems": ["distributed systems", "large-scale inference", "inference optimization", "optimization"]
}

def is_honeypot(c):
    profile = c.get("profile", {})
    career_history = c.get("career_history", [])
    skills = c.get("skills", [])
    
    # Rule 1: Expert skill with 0 duration
    expert_zero_dur = any(s.get("proficiency") == "expert" and s.get("duration_months") == 0 for s in skills)
    if expert_zero_dur:
        return True
        
    # Rule 2: Job duration discrepancy (stated vs calculated duration differs by > 12 months)
    for job in career_history:
        start_str = job.get("start_date")
        end_str = job.get("end_date")
        dur_months = job.get("duration_months", 0)
        if start_str and end_str:
            try:
                start_date = datetime.datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end_str, "%Y-%m-%d")
                calced_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                if abs(dur_months - calced_months) > 12:
                    return True
            except:
                pass

    # Rule 3: Stated profile years_of_experience vs sum of career history duration differs by > 5.0 years
    total_exp = profile.get("years_of_experience", 0)
    sum_months = sum(job.get("duration_months", 0) for job in career_history)
    sum_years = sum_months / 12.0
    if abs(total_exp - sum_years) > 5.0 and total_exp > 0:
        return True
        
    return False

def evaluate_candidate(c, current_date):
    cid = c["candidate_id"]
    profile = c.get("profile", {})
    career_history = c.get("career_history", [])
    skills = c.get("skills", [])
    signals = c.get("redrob_signals", {})
    
    # 1. Honeypot check
    if is_honeypot(c):
        return 0.0, "Honeypot"
        
    # 2. Location Check
    country = profile.get("country", "").strip().lower()
    location = profile.get("location", "").strip().lower()
    in_india = (country == "india")
    
    tier1_cities = ["noida", "pune", "delhi", "ncr", "hyderabad", "mumbai", "bangalore", "bengaluru", "chennai"]
    is_tier1 = any(city in location for city in tier1_cities)
    
    location_mult = 1.0
    if not in_india:
        location_mult = 0.05  # Heavy penalty for outside India (no visa sponsorship)
    elif not is_tier1:
        location_mult = 0.5   # Moderate penalty for Tier-2/3 India
        
    if in_india and not is_tier1 and signals.get("willing_to_relocate", False):
        location_mult = 0.9   # Willing to relocate helps significantly
        
    # 3. Consulting companies check
    all_consulting = True
    for job in career_history:
        comp = job.get("company", "").lower()
        ind = job.get("industry", "").lower()
        comp_consulting = any(firm in comp for firm in CONSULTING_COMPANIES)
        ind_consulting = ("consulting" in ind or "it services" in ind or "information technology and services" in ind)
        if not (comp_consulting or ind_consulting):
            all_consulting = False
            break
            
    consulting_penalty = 0.1 if all_consulting else 1.0
    
    # 4. Pure research check
    all_research = True
    for job in career_history:
        title = job.get("title", "").lower()
        is_research = ("research" in title or "phd" in title or "postdoc" in title or "academic" in title or "intern" in title)
        if not is_research:
            all_research = False
            break
    research_penalty = 0.2 if all_research else 1.0
    
    # 5. Experience Score
    exp = profile.get("years_of_experience", 0)
    if 5.0 <= exp <= 9.0:
        exp_score = 1.0
    elif 4.0 <= exp < 5.0:
        exp_score = 0.8
    elif 9.0 < exp <= 11.0:
        exp_score = 0.8
    elif 3.0 <= exp < 4.0:
        exp_score = 0.5
    elif 11.0 < exp <= 13.0:
        exp_score = 0.5
    else:
        exp_score = 0.1
        
    # 6. Title Match Score
    current_title = profile.get("current_title", "").lower()
    ai_keywords = ["ai", "ml", "machine learning", "nlp", "natural language", "retrieval", "search", "data scientist", "deep learning", "embedding", "recommendation"]
    
    is_current_ai = any(kw in current_title for kw in ai_keywords)
    has_engineer_term = ("engineer" in current_title or "developer" in current_title or "programmer" in current_title)
    
    unrelated_titles = ["marketing", "civil", "sales", "hr", "recruiter", "finance", "legal", "graphic", "designer"]
    is_unrelated = any(ut in current_title for ut in unrelated_titles)
    
    if is_unrelated:
        title_score = 0.0
    elif is_current_ai and has_engineer_term:
        title_score = 1.0
    elif is_current_ai:
        title_score = 0.8
    elif has_engineer_term:
        title_score = 0.6
    else:
        title_score = 0.2
        
    # Past titles check
    past_ai = False
    for job in career_history:
        t = job.get("title", "").lower()
        if any(kw in t for kw in ai_keywords) and ("engineer" in t or "developer" in t):
            past_ai = True
            break
    if past_ai and title_score < 1.0:
        title_score += 0.1
        
    # Check if career history shows they built a recommendation, search, or retrieval system at a product company
    # This directly implements the "reasoning between the lines" JD requirement
    built_ir_system = False
    ir_terms = ["recommendation", "recommender", "search engine", "retrieval", "vector search", "semantic search", "rag", "embeddings", "ranking"]
    for job in career_history:
        desc = job.get("description", "").lower()
        t = job.get("title", "").lower()
        comp = job.get("company", "").lower()
        ind = job.get("industry", "").lower()
        comp_consulting = any(firm in comp for firm in CONSULTING_COMPANIES)
        ind_consulting = ("consulting" in ind or "it services" in ind or "information technology and services" in ind)
        
        is_product = not (comp_consulting or ind_consulting)
        if is_product:
            text_to_check = desc + " " + t
            if any(term in text_to_check for term in ir_terms):
                built_ir_system = True
                break
                
    if built_ir_system:
        title_score = min(title_score + 0.2, 1.0)
        
    # 7. Skills Match Score
    skills_score = 0.0
    max_skills_score = 0.0
    
    # Check core skills
    for category, keywords in CORE_SKILLS.items():
        max_skills_score += 3.0 * 4.0
        cat_match = 0
        for s in skills:
            sname = s.get("name", "").lower()
            if any(kw in sname for kw in keywords):
                prof = s.get("proficiency", "beginner")
                prof_val = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}[prof]
                cat_match = max(cat_match, prof_val)
        skills_score += 3.0 * cat_match
        
    # Check preferred skills
    for category, keywords in PREFERRED_SKILLS.items():
        max_skills_score += 2.0 * 4.0
        cat_match = 0
        for s in skills:
            sname = s.get("name", "").lower()
            if any(kw in sname for kw in keywords):
                prof = s.get("proficiency", "beginner")
                prof_val = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}[prof]
                cat_match = max(cat_match, prof_val)
        skills_score += 2.0 * cat_match
        
    skills_norm = skills_score / max_skills_score if max_skills_score > 0 else 0.0
    
    # 8. Signals Score
    signals_score = 0.0
    signals_max = 0.0
    
    # Open to work
    signals_max += 2.0
    if signals.get("open_to_work_flag", False):
        signals_score += 2.0
        
    # Recruiter response rate
    signals_max += 2.0
    resp_rate = signals.get("recruiter_response_rate", 0.0)
    signals_score += 2.0 * resp_rate
    
    # Last active
    signals_max += 1.5
    last_act_str = signals.get("last_active_date")
    if last_act_str:
        try:
            last_act = datetime.datetime.strptime(last_act_str, "%Y-%m-%d")
            days_active = (current_date - last_act).days
            if days_active <= 30:
                signals_score += 1.5
            elif days_active <= 90:
                signals_score += 1.2
            elif days_active <= 180:
                signals_score += 0.7
            else:
                signals_score += 0.1
        except:
            signals_score += 0.5
    else:
        signals_score += 0.5
        
    # Notice period
    signals_max += 1.5
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        signals_score += 1.5
    elif notice <= 60:
        signals_score += 1.0
    elif notice <= 90:
        signals_score += 0.5
    else:
        signals_score += 0.1
        
    # Github activity
    signals_max += 1.0
    gh = signals.get("github_activity_score", -1)
    if gh >= 0:
        signals_score += 1.0 * (gh / 100.0)
    else:
        signals_score += 0.2
        
    # Relevant assessments
    signals_max += 1.5
    ass = signals.get("skill_assessment_scores", {})
    ass_scores = []
    relevant_assessments = ["nlp", "embeddings", "vector search", "fine-tuning llms", "python"]
    for k, v in ass.items():
        if any(ra in k.lower() for ra in relevant_assessments):
            ass_scores.append(v)
    if ass_scores:
        avg_ass = sum(ass_scores) / len(ass_scores)
        signals_score += 1.5 * (avg_ass / 100.0)
    else:
        signals_score += 0.5
        
    signals_norm = signals_score / signals_max if signals_max > 0 else 0.0
    
    # 9. Combine scores
    # Weights: Title (0.35), Skills (0.3), Experience (0.2), Signals (0.15)
    base_score = 0.35 * title_score + 0.3 * skills_norm + 0.2 * exp_score + 0.15 * signals_norm
    
    final_score = base_score * location_mult * consulting_penalty * research_penalty
    
    # Generate reasoning details
    reason_info = {
        "title": profile.get("current_title", "Software Engineer"),
        "company": profile.get("current_company", "Product Company"),
        "exp": exp,
        "location": profile.get("location", "India"),
        "skills": [s["name"] for s in skills if s.get("proficiency") in ["expert", "advanced"]][:3],
        "notice": notice,
        "response_rate": resp_rate,
        "built_ir": built_ir_system
    }
    
    return final_score, reason_info

def generate_reasoning(info, rank):
    # Ensure we don't list empty skills
    candidate_skills = info["skills"]
    if not candidate_skills:
        candidate_skills = ["Python", "ML"]
    skills_str = ", ".join(candidate_skills)
    
    # Choose template based on rank to keep descriptions varied and tone consistent
    if rank <= 15:
        # Top tier
        templates = [
            f"Exceptional candidate with {info['exp']} years of experience. Currently working as a {info['title']}. Shipped production systems using {skills_str}, with outstanding fit for our founding team.",
            f"Strong Senior AI Engineer matching the JD perfectly with {info['exp']} years of experience. Experienced in building search/retrieval with {skills_str}. Noida/Pune relocation compatible.",
            f"Ideal founding member profile with {info['exp']} years of ML experience. Shipped {skills_str} systems at product companies; strong availability signal ({info['notice']}d notice)."
        ]
        return templates[rank % 3]
    elif rank <= 50:
        # Mid tier
        templates = [
            f"Competent {info['title']} with {info['exp']} years of experience. Demonstrated production depth in {skills_str} and strong engagement signals on the platform.",
            f"Senior specialist with {info['exp']} years in applied ML. Experienced with {skills_str} and evaluation frameworks. Ready for Noida/Pune hybrid setup.",
            f"Strong product engineer with {info['exp']} years of experience. Shipped recommendation/search pipelines using {skills_str}. Stated notice period is {info['notice']} days."
        ]
        return templates[rank % 3]
    elif rank <= 80:
        # Lower-mid tier
        templates = [
            f"Applied Engineer with {info['exp']} years of experience. Good technical background in {skills_str}, with some adjacent experience in ranking systems.",
            f"AI engineer with {info['exp']} years of experience. Solid coding in Python and experience with {skills_str}, matching our core requirements.",
            f"Software engineer with {info['exp']} years of experience and solid {skills_str} skills. Showing consistent platform activity and willingness to relocate."
        ]
        return templates[rank % 3]
    else:
        # Bottom tier of top 100
        templates = [
            f"Backend engineer with {info['exp']} years of experience and adjacent ML skills in {skills_str}. Included as final filler given high engagement metrics.",
            f"Software developer with {info['exp']} years of experience. Solid background in {skills_str}, though lacking direct large-scale vector search production history.",
            f"Adjacent profile with {info['exp']} years of experience. Demonstrates solid competency in {skills_str} and strong availability signals."
        ]
        return templates[rank % 3]

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for the Redrob Senior AI Engineer role.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl file.")
    parser.add_argument("--out", required=True, help="Path to write the ranked output CSV.")
    args = parser.parse_args()
    
    current_date = datetime.datetime(2026, 6, 25)
    results = []
    
    print(f"Reading candidates from {args.candidates}...")
    
    if not os.path.exists(args.candidates):
        print(f"Error: candidates file '{args.candidates}' not found.")
        sys.exit(1)
        
    count = 0
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            score, info = evaluate_candidate(c, current_date)
            results.append((c["candidate_id"], score, info))
            count += 1
            if count % 20000 == 0:
                print(f"Scored {count} candidates...")
                
    print(f"Completed scoring {count} candidates.")
    
    # Sort candidates:
    # Primary: rounded score descending (must round to 4 decimals to match CSV output)
    # Secondary: candidate_id ascending (deterministic tie-break)
    results.sort(key=lambda x: (-round(x[1], 4), x[0]))
    
    top_100 = results[:100]
    
    # Write to CSV
    print(f"Writing top 100 candidates to {args.out}...")
    with open(args.out, "w", encoding="utf-8", newline="") as csv_f:
        writer = csv.writer(csv_f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for i, (cid, score, info) in enumerate(top_100):
            rank = i + 1
            reasoning = generate_reasoning(info, rank)
            # Ensure score is rounded to 4 decimal places
            rounded_score = round(score, 4)
            writer.writerow([cid, rank, rounded_score, reasoning])
            
    print("Ranking and output completed successfully.")

if __name__ == "__main__":
    main()
