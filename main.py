from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import pandas as pd
from io import BytesIO
import openpyxl
from openpyxl.styles import PatternFill

app = FastAPI(title="Invoice Validation API")

# ----------------------
# Validation Logic
# ----------------------
def validate_invoice(row):
    issues = []

    try:
        if round(row["sell_price"] * row["qty"], 2) != round(row["total_sale_value"], 2):
            issues.append("Total sale mismatch")

        if round(row["cost_price"] * row["qty"], 2) != round(row["total_cost_value"], 2):
            issues.append("Total cost mismatch")

        if round(row["total_sale_value"] - row["total_cost_value"], 2) != round(row["profit"], 2):
            issues.append("Profit mismatch")

        if row["qty"] <= 0:
            issues.append("Invalid quantity")

    except Exception as e:
        issues.append(f"Validation error: {e}")

    return issues

# ----------------------
# API Endpoint
# ----------------------
@app.post("/upload_invoices")
async def upload_invoices(file: UploadFile = File(...)):

    if not file.filename.endswith((".json", ".csv")):
        raise HTTPException(status_code=400, detail="Only JSON or CSV files supported")

    content = await file.read()

    try:
        df = pd.read_json(BytesIO(content)) if file.filename.endswith(".json") else pd.read_csv(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File read error: {e}")

    # Duplicate detection
    df["is_duplicate"] = df.duplicated(subset=["invoice_number", "part_number"], keep=False)

    # Rule validation
    df["Issue Type"] = df.apply(validate_invoice, axis=1)

    # Add duplicate flag
    df.loc[df["is_duplicate"], "Issue Type"] = df.loc[
        df["is_duplicate"], "Issue Type"
    ].apply(lambda x: x + ["Duplicate invoice"])

    # Clean output
    df["Issue Type"] = df["Issue Type"].apply(lambda x: ", ".join(x) if x else "")
    df["Status"] = df["Issue Type"].apply(lambda x: "Valid" if x == "" else "Invalid")

    df.drop(columns=["is_duplicate"], inplace=True)

    # Excel export
    output_file = f"validated_{file.filename.split('.')[0]}.xlsx"
    df.to_excel(output_file, index=False)

    # Excel formatting
    wb = openpyxl.load_workbook(output_file)
    ws = wb.active

    red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    status_col = [cell.value for cell in ws[1]].index("Status") + 1

    for row in ws.iter_rows(min_row=2):
        fill = red if row[status_col - 1].value == "Invalid" else green
        for cell in row:
            cell.fill = fill

    wb.save(output_file)

    return FileResponse(
        output_file,
        filename=output_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/")
def health_check():
    return {"status": "Invoice Validation API running"}
