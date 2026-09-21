"""Extract both project workbooks into compact Parquet and CSV caches."""
import argparse
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

SECTOR_SHEETS = [
    "Energy", "Communications", "Consumer, Non-cyclical", "Industrial",
    "Financial", "Consumer, Cyclical", "Technology", "Utilities",
    "Basic Materials", "Diversified",
]

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def sheet_map(z: zipfile.ZipFile) -> dict:
    """Map sheet display name -> xl/worksheets/sheetN.xml path."""
    wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")
    meta = re.findall(r'<sheet name="([^"]+)"[^>]*r:id="(rId\d+)"', wb)
    rel = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(worksheets/[^"]+)"', rels))
    return {name: "xl/" + rel[rid] for name, rid in meta if rid in rel}


def shared_strings(z: zipfile.ZipFile) -> list:
    out = []
    try:
        with z.open("xl/sharedStrings.xml") as f:
            for _, el in ET.iterparse(f):
                if el.tag == NS + "si":
                    out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                    el.clear()
    except KeyError:
        pass
    return out


def col_letters_to_idx(ref: str) -> int:
    """'BC12' -> 0-based column index of 'BC'."""
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return n - 1


def parse_sheet(z: zipfile.ZipFile, path: str, ss: list) -> list:
    """Stream a sheet into a list of dict {col_idx: value}."""
    rows = []
    with z.open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag == NS + "row":
                vals = {}
                for c in el:
                    ref = c.attrib.get("r")
                    t = c.attrib.get("t")
                    v = None
                    for ch in c:
                        if ch.tag == NS + "v":
                            v = ch.text
                    if v is None:
                        continue
                    if t == "s":
                        v = ss[int(v)]
                    vals[col_letters_to_idx(ref)] = v
                rows.append(vals)
                el.clear()
    return rows


def to_frame(rows: list, header_row: int = 0, data_start: int = 2,
             date_col: int = 0) -> pd.DataFrame:
    """Build a DataFrame: index = dates (Excel serials in date_col),
    columns = tickers taken from header_row (col B onward)."""
    header = rows[header_row]
    tickers = {idx: name for idx, name in header.items() if idx > 0}
    cols = sorted(tickers)
    recs, dates = [], []
    for r in rows[data_start:]:
        if date_col not in r:
            continue
        try:
            serial = float(r[date_col])
        except (TypeError, ValueError):
            continue
        dates.append(serial)
        recs.append([r.get(c) for c in cols])
    df = pd.DataFrame(recs, columns=[tickers[c] for c in cols])
    df = df.apply(pd.to_numeric, errors="coerce")
    df.index = pd.to_datetime(dates, unit="D", origin="1899-12-30")
    df.index.name = "date"
    return df


def extract_market(prefix: str, workbook: str, direct_sectors: bool) -> None:
    """Extract one market workbook using its native sheet XML."""
    z = zipfile.ZipFile(RAW / workbook)
    smap = sheet_map(z)
    ss = shared_strings(z)
    print(f"\n{prefix.upper()} sheets:", list(smap))

    # Company names are stored below the ticker headers.
    rows = parse_sheet(z, smap["Price"], ss)
    header, names_row = rows[0], rows[1]
    names = pd.Series({header[i]: names_row.get(i) for i in header if i > 0},
                      name="name")
    names.index.name = "ticker"
    names.to_csv(CACHE / f"{prefix}_names.csv")

    monthly = to_frame(rows)
    monthly.to_parquet(CACHE / f"{prefix}_prices_monthly.parquet")
    print("monthly prices:", monthly.shape, monthly.index.min(), monthly.index.max())

    # Positive monthly weights define point-in-time membership.
    peso_rows = parse_sheet(z, smap["Peso"], ss)
    peso = to_frame(peso_rows)
    peso.to_parquet(CACHE / f"{prefix}_weights_monthly.parquet")
    print("weights:", peso.shape)

    if direct_sectors:
        rows_s = parse_sheet(z, smap["Sector"], ss)
        sector_of = {
            rows_s[0][column]: value
            for column, value in rows_s[2].items()
            if column in rows_s[0]
        }
    else:
        # The S&P sector flags are shifted one column relative to their headers.
        header = peso_rows[0]
        master = [header[c] for c in sorted(k for k in header if k > 0)]
        sector_of = {}
        for sector in SECTOR_SHEETS:
            rows_s = parse_sheet(z, smap[sector], ss)
            first_data = next(row for row in rows_s[2:] if 0 in row)
            for column, value in first_data.items():
                if column == 0 or column >= len(master):
                    continue
                try:
                    flagged = float(value) > 0
                except (TypeError, ValueError):
                    continue
                if flagged:
                    sector_of[master[column]] = sector
        sector_of.setdefault("MMM UN Equity", "Industrial")
    pd.Series(sector_of, name="sector").rename_axis("ticker").to_csv(
        CACHE / f"{prefix}_sectors.csv")
    print("sectors:", len(sector_of))

    groups = pd.Series("all", index=monthly.columns, name="group")
    if prefix == "stoxx":
        groups = pd.Series(
            {ticker: ticker.split()[-2] for ticker in monthly.columns}, name="group"
        )
    groups.rename_axis("ticker").to_csv(CACHE / f"{prefix}_groups.csv")

    # Benchmark columns are daily/monthly, plus weekly for the S&P workbook.
    ac_rows = parse_sheet(z, smap["AC"], ss)
    benchmark = {}
    layouts = [(0, 1, "daily"), (2, 3, "monthly")]
    if prefix == "spx":
        layouts.append((4, 5, "weekly"))
    for date_column, value_column, label in layouts:
        dates, vals = [], []
        for r in ac_rows[1:]:
            if date_column in r and value_column in r:
                try:
                    dates.append(float(r[date_column]))
                    vals.append(float(r[value_column]))
                except (TypeError, ValueError):
                    continue
        s = pd.Series(vals,
                      index=pd.to_datetime(dates, unit="D", origin="1899-12-30"),
                      name=prefix.upper()).sort_index()
        s = s[~s.index.duplicated()]
        benchmark[label] = s
    if "weekly" not in benchmark:
        benchmark["weekly"] = benchmark["daily"].resample("W-FRI").last()
    for label, series in benchmark.items():
        series.rename_axis("date").to_frame().to_parquet(
            CACHE / f"{prefix}_index_{label}.parquet")
        print(f"index {label}: {len(series)} observations")

    print("parsing 'Price daily' (this takes a few minutes)...")
    daily = to_frame(parse_sheet(z, smap["Price daily"], ss))
    daily.to_parquet(CACHE / f"{prefix}_prices_daily.parquet")
    print("daily prices:", daily.shape, daily.index.min(), daily.index.max())

    # The assignment requires weekly or monthly signals.
    weekly = daily.resample("W-FRI").last()
    weekly.to_parquet(CACHE / f"{prefix}_prices_weekly.parquet")
    print("weekly prices:", weekly.shape)
    z.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["spx", "stoxx", "all"], default="all")
    args = parser.parse_args()
    markets = {
        "spx": ("SPX500 Original.xlsm", False),
        "stoxx": ("Stoxx 600 Originale.xlsm", True),
    }
    selected = markets if args.market == "all" else {args.market: markets[args.market]}
    for prefix, (workbook, direct_sectors) in selected.items():
        extract_market(prefix, workbook, direct_sectors)


if __name__ == "__main__":
    main()
