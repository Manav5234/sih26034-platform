"""Add new rules LMR-2024-004 through 007 to the database."""
import sys, uuid
sys.path.insert(0, "/app")
from datetime import date
from app.database import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

Session = sessionmaker(bind=engine)
db = Session()

ruleset_id = "00000000-0000-0000-0000-000000000010"

new_rules = [
    ("LMR-2024-004", "Rule 8", "All pre-packaged goods", "manufacture_date",
     '{"must_be_present": true, "min_confidence": 0.6, "format": "date"}'),
    ("LMR-2024-005", "Rule 9", "Food products, Beverages, Edible oils, Spices, Confectionery", "expiry_date",
     '{"must_be_present": true, "min_confidence": 0.6, "format": "date"}'),
    ("LMR-2024-006", "Schedule II", "Food products, Beverages, Edible oils, Spices, Confectionery", "nutrition_facts",
     '{"must_be_present": true, "min_confidence": 0.4, "format": "nutrition_panel"}'),
    ("LMR-2024-007", "Rule 10", "Food products, Beverages, Edible oils, Spices, Confectionery, Cosmetics, Medicines", "cautions",
     '{"must_be_present": false, "min_confidence": 0.6}'),
]

for rule_id, clause, applicability, decl, conditions in new_rules:
    existing = db.execute(text(f"SELECT rule_id FROM rules WHERE rule_id = '{rule_id}'")).fetchone()
    if not existing:
        db.execute(text("""
            INSERT INTO rules (rule_id, rule_set_id, source_document, clause, applicability,
                required_declaration, validation_conditions, measurement_requirements, exceptions,
                effective_date, evidence_requirements)
            VALUES (:rid, :rsid, :src, :clause, :app, :decl, :vc, NULL, '[]', :ed, '["OCR"]')
        """), {"rid": rule_id, "rsid": ruleset_id, "src": "Legal Metrology Act, 2009",
               "clause": clause, "app": applicability, "decl": decl,
               "vc": conditions, "ed": str(date(2024, 1, 1))})
        print(f"Inserted {rule_id}")
    else:
        print(f"{rule_id} already exists")

db.commit()

# Verify
result = db.execute(text("SELECT rule_id, required_declaration, applicability FROM rules ORDER BY rule_id"))
for r in result.fetchall():
    print(f"  {r[0]}: {r[1]} ({r[2]})")
db.close()
