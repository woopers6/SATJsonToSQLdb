import json
import sqlite3
import os
from typing import Dict, Any

def create_database(db_path: str = "sat_questions.db"):
    """Create SQLite database with tables for organizing SAT questions"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_uuid TEXT UNIQUE NOT NULL,
        question_id TEXT,
        module TEXT,
        primary_class_cd_desc TEXT,
        difficulty TEXT,
        skill_cd TEXT,
        skill_desc TEXT,
        score_band_range_cd INTEGER,
        program TEXT,
        primary_class_cd TEXT,
        external_id TEXT,
        ibn TEXT,
        p_pcc TEXT,
        create_date INTEGER,
        update_date INTEGER,
        content_type TEXT,
        content_origin TEXT,
        has_stem INTEGER,
        has_rationale INTEGER,
        has_answer_choices INTEGER,
        choice_count INTEGER,
        correct_answer_count INTEGER,
        json_content TEXT,
        UNIQUE(question_uuid)
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_module ON questions(module)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subtopic ON questions(primary_class_cd_desc)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_difficulty ON questions(difficulty)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill ON questions(skill_cd)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_combined ON questions(module, primary_class_cd_desc, difficulty)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_question_id ON questions(question_id)')
    
    # Create summary view for easy categorization
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS question_summary AS
    SELECT 
        module,
        primary_class_cd_desc as subtopic,
        difficulty,
        COUNT(*) as question_count,
        GROUP_CONCAT(DISTINCT skill_desc) as skills_covered
    FROM questions 
    WHERE module IS NOT NULL AND primary_class_cd_desc IS NOT NULL AND difficulty IS NOT NULL
    GROUP BY module, primary_class_cd_desc, difficulty
    ORDER BY module, subtopic, 
             CASE difficulty 
                 WHEN 'E' THEN 1 
                 WHEN 'M' THEN 2 
                 WHEN 'H' THEN 3 
                 ELSE 4 
             END
    ''')
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS skill_breakdown AS
    SELECT 
        module,
        skill_cd,
        skill_desc,
        primary_class_cd_desc as subtopic,
        COUNT(*) as question_count,
        GROUP_CONCAT(DISTINCT difficulty) as difficulty_levels
    FROM questions 
    WHERE skill_desc IS NOT NULL
    GROUP BY module, skill_cd, skill_desc, primary_class_cd_desc
    ORDER BY module, subtopic, skill_desc
    ''')
    
    conn.commit()
    return conn

def extract_content_info(content_data):
    """Extract useful information from the content section"""
    if not content_data or not isinstance(content_data, dict):
        return {
            'content_type': None,
            'content_origin': None,
            'has_stem': False,
            'has_rationale': False,
            'has_answer_choices': False,
            'choice_count': 0,
            'correct_answer_count': 0
        }
    
    content_type = content_data.get('type', 'unknown')
    content_origin = content_data.get('origin', 'unknown')
    
    # Check for various content elements
    has_stem = 'stem' in content_data or 'prompt' in content_data
    has_rationale = 'rationale' in content_data
    
    has_answer_choices = False
    choice_count = 0
    if 'answerOptions' in content_data and content_data['answerOptions']:
        has_answer_choices = True
        choice_count = len(content_data['answerOptions'])
    elif 'answer' in content_data and isinstance(content_data['answer'], dict):
        if 'choices' in content_data['answer']:
            has_answer_choices = True
            choice_count = len(content_data['answer']['choices'])
    
    correct_answer_count = 0
    if 'correct_answer' in content_data and content_data['correct_answer']:
        if isinstance(content_data['correct_answer'], list):
            correct_answer_count = len(content_data['correct_answer'])
        else:
            correct_answer_count = 1
    elif 'keys' in content_data and content_data['keys']:
        correct_answer_count = len(content_data['keys'])
    
    return {
        'content_type': content_type,
        'content_origin': content_origin,
        'has_stem': has_stem,
        'has_rationale': has_rationale,
        'has_answer_choices': has_answer_choices,
        'choice_count': choice_count,
        'correct_answer_count': correct_answer_count
    }

def load_and_categorize_questions(json_file_path: str, db_path: str = "sat_questions.db"):
    """Load JSON file and categorize questions into SQLite database"""
    
    if not os.path.exists(json_file_path):
        print(f"Error: File {json_file_path} not found!")
        return
    
    print(f"Loading questions from {json_file_path}...")
    file_size = os.path.getsize(json_file_path) / (1024 * 1024)  
    print(f"File size: {file_size:.1f} MB")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            print("Parsing JSON file... (this may take a moment for large files)")
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    print(f"Successfully loaded {len(data)} questions from JSON file")
    
    conn = create_database(db_path)
    cursor = conn.cursor()
    
    inserted_count = 0
    skipped_count = 0
    processed_count = 0
    
    print("Processing questions...")
    
    for uuid, question_data in data.items():
        processed_count += 1
        
        if processed_count % 1000 == 0:
            print(f"  Processed {processed_count}/{len(data)} questions...")
        
        try:
            question_id = question_data.get('questionId', '')
            module = question_data.get('module', '').lower() if question_data.get('module') else None
            subtopic = question_data.get('primary_class_cd_desc', '')
            difficulty = question_data.get('difficulty', '')
            skill_cd = question_data.get('skill_cd', '')
            skill_desc = question_data.get('skill_desc', '')
            score_band = question_data.get('score_band_range_cd', 0)
            program = question_data.get('program', '')
            primary_class_cd = question_data.get('primary_class_cd', '')
            external_id = question_data.get('external_id', '')
            ibn = question_data.get('ibn', '')
            p_pcc = question_data.get('pPcc', '')
            create_date = question_data.get('createDate', 0)
            update_date = question_data.get('updateDate', 0)
            
            content_info = extract_content_info(question_data.get('content'))
            
            json_content = json.dumps(question_data, indent=2)
            
            # Insert into database
            cursor.execute('''
            INSERT OR REPLACE INTO questions (
                question_uuid, question_id, module, primary_class_cd_desc, 
                difficulty, skill_cd, skill_desc, score_band_range_cd, 
                program, primary_class_cd, external_id, ibn, p_pcc,
                create_date, update_date, content_type, content_origin,
                has_stem, has_rationale, has_answer_choices, choice_count,
                correct_answer_count, json_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                uuid, question_id, module, subtopic, difficulty, 
                skill_cd, skill_desc, score_band, program, 
                primary_class_cd, external_id, ibn, p_pcc,
                create_date, update_date, content_info['content_type'],
                content_info['content_origin'], content_info['has_stem'],
                content_info['has_rationale'], content_info['has_answer_choices'],
                content_info['choice_count'], content_info['correct_answer_count'],
                json_content
            ))
            
            inserted_count += 1
            
        except Exception as e:
            print(f"Error processing question {uuid}: {e}")
            skipped_count += 1
            continue
    
    conn.commit()
    
    print(f"\n" + "="*60)
    print("DATABASE CREATION COMPLETE!")
    print("="*60)
    print(f"Successfully inserted: {inserted_count:,} questions")
    if skipped_count > 0:
        print(f"Skipped due to errors: {skipped_count:,} questions")
    
    print("\n" + "="*60)
    print("CATEGORIZATION SUMMARY")
    print("="*60)
    
    cursor.execute('SELECT * FROM question_summary')
    results = cursor.fetchall()
    
    current_module = ""
    module_totals = {}
    
    for row in results:
        module, subtopic, difficulty, count, skills = row
        
        if module != current_module:
            if current_module and current_module in module_totals:
                print(f"    {current_module.upper()} TOTAL: {module_totals[current_module]:,} questions\n")
            
            print(f" MODULE: {module.upper() if module else 'UNKNOWN'}")
            current_module = module
            module_totals[module] = 0
        
        module_totals[module] = module_totals.get(module, 0) + count
        
        print(f"  └─ {subtopic if subtopic else 'No Subtopic'}")
        
        difficulty_name = {"E": "Easy", "M": "Medium", "H": "Hard"}.get(difficulty, difficulty if difficulty else "Unknown")
        print(f"     └─ {difficulty_name}: {count:,} questions")
    
    # Print final module total
    if current_module and current_module in module_totals:
        print(f"    {current_module.upper()} TOTAL: {module_totals[current_module]:,} questions")
    
    # Overall statistics
    cursor.execute('SELECT COUNT(*) FROM questions')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT module) FROM questions WHERE module IS NOT NULL')
    modules = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT primary_class_cd_desc) FROM questions WHERE primary_class_cd_desc IS NOT NULL AND primary_class_cd_desc != ""')
    subtopics = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT difficulty) FROM questions WHERE difficulty IS NOT NULL AND difficulty != ""')
    difficulties = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT skill_desc) FROM questions WHERE skill_desc IS NOT NULL AND skill_desc != ""')
    unique_skills = cursor.fetchone()[0]
    
    print(f"\n" + "="*60)
    print(" OVERALL STATISTICS:")
    print("="*60)
    print(f"   Total Questions: {total:,}")
    print(f"   Modules: {modules}")
    print(f"   Subtopics: {subtopics}")
    print(f"   Difficulty Levels: {difficulties}")
    print(f"   Unique Skills: {unique_skills}")
    
    # Content type breakdown
    cursor.execute('''
    SELECT content_type, COUNT(*) 
    FROM questions 
    WHERE content_type IS NOT NULL 
    GROUP BY content_type 
    ORDER BY COUNT(*) DESC
    ''')
    content_types = cursor.fetchall()
    
    if content_types:
        print(f"\n   Content Types:")
        for content_type, count in content_types:
            print(f"     - {content_type}: {count:,}")
    
    conn.close()
    print(f" Database saved as: {db_path}")
    print(f" Database size: {os.path.getsize(db_path) / (1024 * 1024):.1f} MB")

def query_questions(db_path: str = "sat_questions.db", module: str = None, 
                   subtopic: str = None, difficulty: str = None, 
                   skill: str = None, limit: int = 10):
    """Query questions from the database based on criteria"""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Please run the categorization first.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Build query
    where_clauses = []
    params = []
    
    if module:
        where_clauses.append("module = ?")
        params.append(module.lower())
    
    if subtopic:
        where_clauses.append("primary_class_cd_desc LIKE ?")
        params.append(f"%{subtopic}%")
    
    if difficulty:
        where_clauses.append("difficulty = ?")
        params.append(difficulty.upper())
    
    if skill:
        where_clauses.append("skill_desc LIKE ?")
        params.append(f"%{skill}%")
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    query = f'''
    SELECT question_uuid, question_id, module, primary_class_cd_desc, 
           difficulty, skill_desc, content_type
    FROM questions 
    WHERE {where_clause}
    ORDER BY module, primary_class_cd_desc, difficulty
    LIMIT ?
    '''
    
    params.append(limit)
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    print(f"Found {len(results)} questions matching your criteria:")
    print("-" * 100)
    
    for uuid, qid, mod, sub, diff, skill_desc, content_type in results:
        mod_display = mod.upper() if mod else "N/A"
        sub_display = sub if sub else "No Subtopic"
        diff_display = {"E": "Easy", "M": "Medium", "H": "Hard"}.get(diff, diff if diff else "N/A")
        skill_display = skill_desc[:50] + "..." if skill_desc and len(skill_desc) > 50 else (skill_desc or "N/A")
        
        print(f"ID: {qid:8} | {mod_display:7} | {sub_display:15} | {diff_display:6} | {content_type or 'N/A':8} | {skill_display}")
    
    conn.close()

def show_database_stats(db_path: str = "sat_questions.db"):
    """Show detailed statistics about the database"""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("="*60)
    print("DETAILED DATABASE STATISTICS")
    print("="*60)
    
    print("\n SKILL BREAKDOWN BY MODULE:")
    cursor.execute('SELECT * FROM skill_breakdown')
    skills = cursor.fetchall()
    
    current_module = ""
    for module, skill_cd, skill_desc, subtopic, count, difficulties in skills:
        if module != current_module:
            print(f"\n📚 {module.upper() if module else 'UNKNOWN'}:")
            current_module = module
        
        print(f"  {skill_cd:6} | {subtopic:15} | {count:3} questions | {skill_desc}")
    
    conn.close()

# Example usage and main execution
if __name__ == "__main__":
    json_file = "cbquestions.json"  
    db_file = "sat_questions.db"
    
    print("SAT Questions Database Organizer")
    print("=" * 60)
    print("This script will process your 23.3MB JSON file and create a SQLite database")
    print("organized by Module, Subtopic, and Difficulty level.")
    print("=" * 60)
    
    # Check if JSON file exists
    if not os.path.exists(json_file):
        print(f"\n JSON file '{json_file}' not found!")
        print("Please update the 'json_file' variable with the correct path to your JSON file.")
        print("\nExample:")
        print('json_file = "/path/to/your/sat_questions.json"')
    else:
        load_and_categorize_questions(json_file, db_file)
        
        print("\n" + "=" * 60)
        print("EXAMPLE QUERIES:")
        print("=" * 60)
        
        # Example queries
        print("\n1. Math questions with Medium difficulty:")
        query_questions(db_file, module="math", difficulty="M", limit=5)
        
        print("\n2. All Algebra questions:")
        query_questions(db_file, subtopic="Algebra", limit=5)
        
        print("\n3. Questions about linear equations:")
        query_questions(db_file, skill="linear", limit=5)
        
        # Show additional stats
        show_database_stats(db_file)
        