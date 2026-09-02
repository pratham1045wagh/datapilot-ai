import uuid
import os
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
from app.config import UPLOADS_DIR, CLEANED_DIR

class DatasetService:
    @staticmethod
    def generate_dataset_id() -> str:
        return str(uuid.uuid4())

    def save_uploaded_file(self, content: bytes, filename: str) -> Tuple[str, Path, str]:
        """
        Saves uploaded byte stream safely to disk with unique dataset_id.
        Returns (dataset_id, file_path, original_filename).
        """
        dataset_id = self.generate_dataset_id()
        ext = Path(filename).suffix.lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            raise ValueError(f"Unsupported file extension '{ext}'. Only CSV and Excel (.xlsx, .xls) are allowed.")

        safe_filename = f"{dataset_id}_raw{ext}"
        target_path = UPLOADS_DIR / safe_filename
        with open(target_path, "wb") as f:
            f.write(content)

        return dataset_id, target_path, filename

    def load_raw_dataframe(self, dataset_id: str) -> Tuple[pd.DataFrame, str, Path]:
        """
        Loads raw original dataframe by dataset_id.
        """
        for ext in [".csv", ".xlsx", ".xls"]:
            path = UPLOADS_DIR / f"{dataset_id}_raw{ext}"
            if path.exists():
                df = self.read_file_to_dataframe(path, ext)
                return df, ext, path

        raise FileNotFoundError(f"Original uploaded dataset '{dataset_id}' not found.")

    def save_cleaned_dataframe(self, df: pd.DataFrame, dataset_id: str, original_ext: str) -> Path:
        """
        Saves cleaned dataframe to CLEANED_DIR in both .xlsx (with wide columns to prevent Excel ### date overflow) and .csv.
        """
        primary_path = CLEANED_DIR / f"{dataset_id}_cleaned{original_ext}"
        xlsx_path = CLEANED_DIR / f"{dataset_id}_cleaned.xlsx"
        csv_path = CLEANED_DIR / f"{dataset_id}_cleaned.csv"

        save_df = df.copy()
        # Convert any datetime64 or date string columns to clean YYYY-MM-DD representation
        for col in save_df.columns:
            if pd.api.types.is_datetime64_any_dtype(save_df[col]):
                save_df[col] = save_df[col].dt.strftime("%Y-%m-%d")
            else:
                col_lower = str(col).lower()
                if "date" in col_lower or save_df[col].dtype == "object":
                    try:
                        non_nulls = save_df[col].dropna().astype(str)
                        if not non_nulls.empty:
                            parsed = pd.to_datetime(non_nulls, errors="coerce")
                            if parsed.notna().sum() / len(non_nulls) > 0.6:
                                full_parsed = pd.to_datetime(save_df[col], errors="coerce")
                                save_df[col] = full_parsed.dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

        # 1. Save Excel file with generous openpyxl column widths (width >= 20)
        try:
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                save_df.to_excel(writer, index=False)
                sheets = writer.sheets
                sheet = sheets["Sheet1"] if "Sheet1" in sheets else sheets[list(sheets.keys())[0]]
                for col_cells in sheet.columns:
                    max_len = 0
                    col_letter = col_cells[0].column_letter
                    for cell in col_cells:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                    # Set generous width so date values (2019-05-08) never display as ####### in Excel
                    sheet.column_dimensions[col_letter].width = max(max_len + 6, 20)
        except Exception:
            save_df.to_excel(xlsx_path, index=False)

        # 2. Save CSV file
        save_df.to_csv(csv_path, index=False)

        return primary_path if primary_path.exists() else xlsx_path

    def get_cleaned_file_path(self, dataset_id: str, fmt: Optional[str] = None) -> Optional[Tuple[Path, str]]:
        """
        Returns (cleaned_file_path, extension) if cleaned file exists.
        Guarantees .xlsx exists with openpyxl wide column dimensions so dates never show as ####### in Excel.
        """
        xlsx_path = CLEANED_DIR / f"{dataset_id}_cleaned.xlsx"
        csv_path = CLEANED_DIR / f"{dataset_id}_cleaned.csv"

        if fmt and fmt.lower() == "csv":
            if csv_path.exists():
                return csv_path, ".csv"
            elif xlsx_path.exists():
                try:
                    df = pd.read_excel(xlsx_path)
                    df.to_csv(csv_path, index=False)
                    return csv_path, ".csv"
                except Exception:
                    pass

        # Default or format == "xlsx": Prioritize .xlsx with explicit column widths
        if xlsx_path.exists():
            return xlsx_path, ".xlsx"

        # If only CSV exists on disk, convert and generate .xlsx on-the-fly
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                self.save_cleaned_dataframe(df, dataset_id, ".xlsx")
                if xlsx_path.exists():
                    return xlsx_path, ".xlsx"
            except Exception:
                pass
            return csv_path, ".csv"

        return None

    def load_cleaned_dataframe(self, dataset_id: str) -> Tuple[pd.DataFrame, str, Path]:
        """
        Loads cleaned dataframe by dataset_id.
        """
        result = self.get_cleaned_file_path(dataset_id)
        if result:
            cleaned_path, ext = result
            df = self.read_file_to_dataframe(cleaned_path, ext)
            return df, ext, cleaned_path
        raise FileNotFoundError(f"Cleaned dataset '{dataset_id}' not found.")

    def read_file_to_dataframe(self, file_path: Path, ext: str) -> pd.DataFrame:
        if ext.lower() == ".csv":
            # Attempt UTF-8, then fallback to latin1
            try:
                return pd.read_csv(file_path)
            except UnicodeDecodeError:
                return pd.read_csv(file_path, encoding="latin1")
        elif ext.lower() in [".xlsx", ".xls"]:
            return pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format {ext}")

dataset_service = DatasetService()
