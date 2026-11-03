from jev_lite import TypeSafe, Noul
import pandas as pd
from pathlib import Path
import sys
import re


client = TypeSafe()

# -----------------------------
# Configuration
# -----------------------------
AUTO_MAP_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.50
MIN_CONFIDENCE_MARGIN = 0.15
SAMPLE_ROWS_PER_COLUMN = 8

# Standard output fields that JEV should map from supplier CSV columns.
# The order here is also the order used in all_supplier_data.csv.
TARGET_FIELDS = {
    "supplier_product_id": (
        "The supplier's own identifier for a catalog item/product. Examples include "
        "supplier item ID, supplier product ID, item ID, product ID, vendor item ID, "
        "or a supplier SKU when it is clearly the supplier's internal product reference. "
        "Do NOT treat a manufacturer model/model number, manufacturer code, product name, "
        "description, category, price, stock quantity, department, specifications, or "
        "technical details as the supplier product ID."
    ),
    "model_number": (
        "The manufacturer's product model identifier. It stays the same when different "
        "suppliers sell the same manufacturer model. It may contain letters and numbers; "
        "the word 'number' does not mean digits only. Possible source headings include "
        "Model, Model_number, Manufacturer_part_number, or Manufacturer_code, but the "
        "heading alone is not proof. Use the heading together with the sample values and "
        "their relationship to the product descriptions. Do NOT confuse a supplier's own "
        "internal item/product ID with the manufacturer's model number."
    ),
    "product_name": (
        "A readable product name or description that tells what the item is, rather than "
        "only identifying it with a code. It may include the product type, brand, model, "
        "connection, size, or useful features. Possible source headings include "
        "Product_name, Item_name, Description, Item_description, or Title, but the heading "
        "alone is not proof; use the sample values too. A value such as 'Aster K100 Wired "
        "Keyboard' or 'Keyboard, wired; usb-a; full-size; english layout; black - Aster K100' "
        "fits product_name. Do NOT treat a model identifier such as 'Aster K100' by itself, "
        "a supplier/internal ID, or a broad category/department such as 'Accessories' or "
        "'Computer peripherals' as the product name."
    ),
    "category": (
        "A group or department that several products belong to. Possible source "
        "headings include Category, Department, or Product_group. Judge the heading "
        "and sample values together: 'Accessories', 'Computer peripherals', 'Displays', "
        "and 'Keyboards' are groups, while 'Aster K100 Wired Keyboard' is a particular "
        "product name. Preserve the supplier's original category wording. Do NOT "
        "choose a product name, model identifier, or technical specifications."
    ),
    "price_usd": (
        "The price of ONE individual item, confirmed to be in US dollars (USD). "
        "Possible headings include Price_USD, Unit_cost_USD, or Unit_price, but "
        "numeric values such as 15.00 or 14.50 do not establish currency or unit basis. "
        "For the supplied example files, supplier_a.csv Price_USD and supplier_b.csv "
        "Unit_cost_USD are confirmed USD prices per item. For other columns/files, "
        "require evidence of BOTH USD currency and a per-item basis; a bare Price "
        "heading or Unit_price without currency is insufficient. Do NOT select "
        "prices in other currencies, per-box prices, totals, or quantities. If a "
        "column plausibly contains prices but currency or unit basis is unknown, "
        "score it between 0.50 and 0.84 so it requires human review."
    ),
    "stock_quantity": (
        "How many individual units the supplier currently has available. Possible "
        "headings include Stock_quantity, Units_available, or Available_stock. Use "
        "the heading and sample values together; values such as 0, 17, and 50 fit "
        "available unit counts only when the meaning is established. Zero means "
        "none available; a blank means unknown and must remain blank. Do NOT select "
        "units ordered, units sold, boxes available, package sizes, or prices. If "
        "a plausible quantity column has unclear availability or unit basis, score "
        "it between 0.50 and 0.84 so it requires human review."
    ),
    "specifications": (
        "Technical features describing the product, such as connection type, "
        "capacity, dimensions, speed, or layout. Possible headings include "
        "Specifications, Technical_details, or Specs. Sample values such as "
        "'Wired; USB-A; full-size; English layout' describe specifications. A "
        "description can also contain technical features, but when a separate "
        "technical-details column exists, prefer that clearer source and score "
        "the general description lower. Do NOT choose a category, model code, "
        "supplier item ID, price, or stock quantity. Preserve the source text."
    ),
}

# Example folder structure:
# Jev/
#   jev.py
#   data/
#       18-10-2026/
#           supplier_a.csv
#           supplier_b.csv
#   output/
#
# Run with:
# python jev.py 18-10-2026
if len(sys.argv) < 2:
    raise ValueError(
        "Please provide the data folder name. Example: python jev.py 18-10-2026"
    )

# Keep the folder name exactly as the user typed it.
folder_name = sys.argv[1]

# Folder where jev.py itself is located.
project_folder = Path(__file__).resolve().parent

# Input folder: Jev/data/<folder_name>
data_folder = project_folder / "data" / folder_name

# Output folder: Jev/output/<folder_name>
output_folder = project_folder / "output" / folder_name

if not data_folder.exists():
    raise FileNotFoundError(f"Data folder not found: {data_folder}")

# Create output/<folder_name> automatically if it does not exist.
output_folder.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helper functions
# -----------------------------
def get_supplier_code(csv_name):
    """
    Examples:
        supplier_a.csv     -> A
        supplier_b.csv     -> B
        supplier_a(1).csv  -> A
    """
    stem = Path(csv_name).stem.strip()
    stem = re.sub(r"\(\d+\)$", "", stem).strip()

    match = re.search(r"supplier[\s_-]*([A-Za-z0-9]+)$", stem, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Fallback: keep the file stem if the file does not follow supplier_a naming.
    return stem.upper()


def get_sample_values(series, limit=SAMPLE_ROWS_PER_COLUMN):
    """Return up to `limit` non-empty sample values from one source column."""
    samples = []

    for value in series.dropna():
        text = str(value).strip()
        if not text:
            continue

        samples.append(text)
        if len(samples) >= limit:
            break

    return samples


def find_target_column(df, csv_name, target_field, target_definition):
    """
    Ask JEV to score every source column for one standard target field.

    Returns:
        source_column
        best_candidate
        confidence
        second_best_confidence
        confidence_margin
        status

    status can be:
        auto_mapped
        human_review
        no_match
    """
    if df.empty or len(df.columns) == 0:
        return {
            "source_column": None,
            "best_candidate": None,
            "confidence": 0.0,
            "second_best_confidence": 0.0,
            "confidence_margin": 0.0,
            "status": "no_match",
        }

    questions = {}
    question_to_column = {}

    # Build one JEV question for every source column.
    for index, column_name in enumerate(df.columns):
        samples = get_sample_values(df[column_name])
        sample_text = str(samples) if samples else "[]"
        question_key = f"candidate_{index}"
        question_to_column[question_key] = column_name

        questions[question_key] = Noul(
            instructions=(
                f"Does the source column '{column_name}' represent the standard target "
                f"field '{target_field}'? Sample values: {sample_text}. "
                "Judge the column name and sample values together. Return high confidence "
                "only when this column truly represents the target meaning."
            )
        )

    state = (
        f"CSV file: {csv_name}\n"
        f"Target field: {target_field}\n"
        f"Target definition: {target_definition}\n"
        f"All source headings: {list(df.columns)}\n"
        "Evaluate every candidate column independently."
    )

    try:
        result = client.system_one.create(
            state=state,
            questions=questions,
        )
    except Exception:
        # If the AI call fails, do not guess.
        return {
            "source_column": None,
            "best_candidate": None,
            "confidence": 0.0,
            "second_best_confidence": 0.0,
            "confidence_margin": 0.0,
            "status": "human_review",
        }

    # Collect JEV's confidence score for every source column.
    scores = []

    for question_key, column_name in question_to_column.items():
        try:
            confidence = float(result.nouls[question_key].noul)
        except (KeyError, TypeError, ValueError, AttributeError):
            confidence = 0.0

        scores.append((column_name, confidence))

    scores.sort(key=lambda item: item[1], reverse=True)

    best_candidate, best_confidence = scores[0]
    second_best_confidence = scores[1][1] if len(scores) > 1 else 0.0
    confidence_margin = best_confidence - second_best_confidence

    # Auto-map only when JEV is highly confident AND the winning column is
    # clearly better than the second-best candidate.
    if (
        best_confidence >= AUTO_MAP_THRESHOLD
        and confidence_margin >= MIN_CONFIDENCE_MARGIN
    ):
        return {
            "source_column": best_candidate,
            "best_candidate": best_candidate,
            "confidence": best_confidence,
            "second_best_confidence": second_best_confidence,
            "confidence_margin": confidence_margin,
            "status": "auto_mapped",
        }

    # Medium confidence: propose the best candidate but leave the output empty
    # until a human reviews the mapping.
    if best_confidence >= REVIEW_THRESHOLD:
        return {
            "source_column": None,
            "best_candidate": best_candidate,
            "confidence": best_confidence,
            "second_best_confidence": second_best_confidence,
            "confidence_margin": confidence_margin,
            "status": "human_review",
        }

    # Low confidence: no reliable matching source column was found.
    return {
        "source_column": None,
        "best_candidate": best_candidate,
        "confidence": best_confidence,
        "second_best_confidence": second_best_confidence,
        "confidence_margin": confidence_margin,
        "status": "no_match",
    }


# -----------------------------
# Read suppliers and map fields
# -----------------------------
processed_dataframes = []
mapping_review_rows = []

for csv_path in sorted(data_folder.glob("*.csv")):
    csv_name = csv_path.name
    supplier_code = get_supplier_code(csv_name)

    # Read the original supplier data once.
    source_df = pd.read_csv(csv_path)

    # Important: JEV evaluates only the ORIGINAL supplier columns.
    # We calculate all target mappings before adding our standard output columns.
    mappings = {}

    for target_field, target_definition in TARGET_FIELDS.items():
        mappings[target_field] = find_target_column(
            source_df,
            csv_name,
            target_field,
            target_definition,
        )

    # Build a CLEAN standardized output dataframe.
    # We intentionally do NOT copy the supplier's original columns into the output.
    df = pd.DataFrame(index=source_df.index)

    # Standard column 1: supplier
    df["supplier"] = supplier_code

    # Standard mapped columns, in TARGET_FIELDS order.
    for target_field in TARGET_FIELDS:
        mapping = mappings[target_field]

        if mapping["status"] == "auto_mapped" and mapping["source_column"] is not None:
            df[target_field] = source_df[mapping["source_column"]].copy()
        else:
            # Never guess for human_review or no_match.
            df[target_field] = pd.Series(pd.NA, index=source_df.index, dtype="object")

        # One audit/review row per supplier + target field.
        mapping_review_rows.append(
            {
                "supplier": supplier_code,
                "file_name": csv_name,
                "target_field": target_field,
                "selected_source_column": mapping["source_column"],
                "best_candidate_column": mapping["best_candidate"],
                "confidence": round(mapping["confidence"], 4),
                "second_best_confidence": round(
                    mapping["second_best_confidence"], 4
                ),
                "confidence_margin": round(mapping["confidence_margin"], 4),
                "status": mapping["status"],
                "needs_human_review": mapping["status"] == "human_review",
            }
        )

    processed_dataframes.append(df)

    # Debug prints intentionally kept commented out.
    # print(f"Loaded: {csv_name}")
    # print(f"Supplier: {supplier_code}")
    # print(f"Mappings: {mappings}")

if not processed_dataframes:
    raise ValueError(f"No CSV files found inside: {data_folder}")


# -----------------------------
# Combine all suppliers vertically
# -----------------------------
# Supplier A rows first, then Supplier B rows, etc.
# The final file contains ONLY the standardized output columns.
combined_df = pd.concat(
    processed_dataframes,
    axis=0,
    ignore_index=True,
    sort=False,
)

# Keep exactly these standardized fields, in this fixed order.
standard_columns = ["supplier"] + list(TARGET_FIELDS.keys())
combined_df = combined_df[standard_columns]

# Save the combined supplier data.
output_csv = output_folder / "all_supplier_data.csv"
combined_df.to_csv(output_csv, index=False)

# Save one mapping-audit file for all standard target fields.
mapping_review_df = pd.DataFrame(mapping_review_rows)
mapping_review_csv = output_folder / "field_mapping_review.csv"
mapping_review_df.to_csv(mapping_review_csv, index=False)

# Output prints intentionally disabled.
# print(f"Combined CSV created: {output_csv}")
# print(f"Mapping review created: {mapping_review_csv}")
