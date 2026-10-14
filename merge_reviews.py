from pathlib import Path
import sys

import pandas as pd


# Dat file nay o thu muc goc Crawl_Data, cung cap voi thu muc data/.
PROJECT_ROOT = Path(__file__).resolve().parent
REVIEWS_DIR = PROJECT_ROOT / "data" / "reviews"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw_data.csv"


def is_sequential_index(series: pd.Series) -> bool:
    """Nhan dien cot index co ten 'index'/'level_0' va gia tri tang deu."""
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        return False

    actual = values.to_numpy()
    count = len(actual)
    if count == 0:
        return False

    zero_based = (actual == list(range(count))).all()
    one_based = (actual == list(range(1, count + 1))).all()
    return bool(zero_based or one_based)


def remove_saved_index_column(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Chi bo cot index phat sinh khi luu CSV; khong sua cac cot du lieu khac."""
    columns_to_drop = []

    for column in df.columns:
        normalized = str(column).strip().lower()

        # pandas thuong tao cot 'Unnamed: 0' khi CSV duoc luu voi index=True.
        if normalized.startswith("unnamed:"):
            columns_to_drop.append(column)
        # Mot so file co the dat ten cot index la 'index' hoac 'level_0'.
        elif normalized in {"index", "level_0"} and is_sequential_index(df[column]):
            columns_to_drop.append(column)

    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)

    return df, [str(column) for column in columns_to_drop]


def main() -> None:
    if not REVIEWS_DIR.is_dir():
        sys.exit(f"Khong tim thay thu muc: {REVIEWS_DIR}")

    csv_files = sorted(REVIEWS_DIR.glob("*.csv"))
    if not csv_files:
        sys.exit(f"Khong tim thay file CSV nao trong: {REVIEWS_DIR}")

    dataframes = []
    total_rows = 0

    for csv_file in csv_files:
        df = pd.read_csv(csv_file, encoding="utf-8-sig", low_memory=False)
        original_rows = len(df)
        df, removed_columns = remove_saved_index_column(df)
        total_rows += original_rows
        dataframes.append(df)

        message = f"[OK] {csv_file.name}: {original_rows:,} dong"
        if removed_columns:
            message += f" | da bo cot index: {', '.join(removed_columns)}"
        else:
            message += " | khong phat hien cot index can bo"
        print(message)

    # Gop theo hang; khong xoa dong trung lap va khong lam sach noi dung.
    raw_data = pd.concat(dataframes, ignore_index=True, sort=False)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # index=False de khong tao them cot index trong raw_data.csv.
    raw_data.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print("\nHoan tat gop du lieu.")
    print(f"So file CSV: {len(csv_files):,}")
    print(f"Tong so dong doc tu cac file: {total_rows:,}")
    print(f"So dong trong raw_data.csv: {len(raw_data):,}")
    print(f"So cot sau khi gop: {len(raw_data.columns):,}")
    print(f"Cac cot: {', '.join(map(str, raw_data.columns))}")
    print(f"File dau ra: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
