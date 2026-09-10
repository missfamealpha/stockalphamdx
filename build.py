#!/usr/bin/env python3
"""
ดึงข้อมูลสต็อกจาก Google Sheet -> จัดหมวดหมู่ -> เขียน data.json ให้หน้าเว็บ index.html อ่าน

ใช้งาน:
    python3 build.py                  # ดึงจากชีตจริง
    python3 build.py --csv ไฟล์.csv    # ใช้ไฟล์ CSV ที่มีอยู่ (ทดสอบแบบไม่ต่อเน็ต)
    python3 build.py --force          # ข้ามการตรวจว่าข้อมูลหายไปเยอะ (ใช้เมื่อรู้ตัวว่าชีตถูกลบจริง)

ไม่ต้องติดตั้งอะไรเพิ่ม ใช้ standard library ล้วน
"""

import argparse, csv, datetime, io, json, os, sys, urllib.request
from collections import Counter, OrderedDict

# ---------------------------------------------------------------- config
SHEET_ID  = os.environ.get("SHEET_ID", "18p59fU78rGJamuDsVmx5HXOMwzrEOW6qS0lLJv-iX44")
GID       = os.environ.get("SHEET_GID", "0")
OUT       = os.environ.get("OUT_JSON", "data.json")
MIN_ROWS  = int(os.environ.get("MIN_ROWS", "100"))   # น้อยกว่านี้ = ผิดปกติ หยุดทันที
MAX_DROP  = float(os.environ.get("MAX_DROP", "0.20"))  # ลดจากรอบก่อนเกิน 20% = หยุด

SHEET_URL = ("https://docs.google.com/spreadsheets/d/{}/gviz/tq"
             "?tqx=out:csv&gid={}").format(SHEET_ID, GID)

# ---------------------------------------------------------------- หมวดหมู่
CATS = [
 ("rapid", "Rapid Test", [
   "rapid","hbsag","hcv","hiv","syphilis","dengue","malaria","maralai","influenza","covid","panbio",
   "fob","fecal occult","met rapid","cryptococcus","rpr","verotest","gonorrhea","chlamydia","hav",
   "tppa","thc screening","morphine","metamphetamine","pregnancy","determine","sp10","chase buffer",
   "tb lam","ชุดตรวจ","น้ำยาตรวจ anti-hiv","screening","antigen","self test","bioline","synthgene","checknow"]),
 ("chem", "เคมีคลินิก", [
   "glucose","urea","bun","creatinine","bilrubin","bilirubin","protien","protein","albumin","alkalinephos",
   "asat","alat","hdl","triglyceride","uric acid","ldl","hba1c","wash solution","trulab","trucal","lh","buffer"]),
 ("hema", "CBC", [
   "cellpack","sulfolyser","fluorocell","lysercell","xnl check","m53","5mdr","cbc "]),
 ("consum", "วัสดุสิ้นเปลือง", [
   "ถุงมือ","gloves","กระปุกเก็บตัวอย่าง","เข็มเจาะ","lancet","capillary","urine container","urine bag",
   "สำลี","ซองซิป","แผ่นปิดแผล","พลาสเตอร์","แผ่นฟิล์ม","แผ่นตรวจสอบการฆ่าเชื้อ","แผ่นรองซับ",
   "วัสดุสื้นเปลือง","วัสดุสิ้นเปลือง"]),
 ("device", "อุปกรณ์", [
   "เครื่องวัดความดัน","เครื่องเป่าแอลกอฮอล์","รถเข็น","wheelchair","ไม้เท้า","ไม้ค้ำยัน","เฝือก","เตียง",
   "cpap","bpap","เครื่องผลิตออกซิเจน","ที่นอนลม","เบาะรองนั่ง","เครื่องช่วยเดิน","เครื่องตรวจน้ำตาล",
   "เครื่องวัดไข้","พาร์ดิชั่น","เข็มขัดห้ามเลือด","สายรัดรถเข็น","at8070"]),
 ("service", "แพ็คเกจ/บริการ", [
   "แพคเกจ","เเพคเกจ","package","ระบบเชื่อมต่อ","ค่าเชื่อมต่อ","clinical trial","ระบบ lis"]),
 ("admin", "ค่าใช้จ่าย", [
   "ค่าไฟฟ้า","ค่าจ้าง","ค่าซ่อมแซม","ค่าโทรศัพท์","ค่าจัดส่ง","delivery fee","ค่าอาหาร","ค่าเครื่องเขียน",
   "กองทุนเงินทดแทน","เครื่องสำรองไฟ","คอมพิวเตอร์","เครื่องแสกนลายนิ้วมือ","ค่าดำเนินการหนังสือ"]),
]
ORDER    = ["rapid","chem","hema","consum","device","service","admin","other"]
NONSTOCK = ["service","admin","other"]
LABELS   = {k: l for k, l, _ in CATS}
LABELS["other"] = "อื่นๆ"

# ชื่อที่ตรวจแล้วว่า "น่าจะซ้ำกัน" ในชีต (คัดด้วยมือ ไม่ใช่ auto)
DUP_GROUPS = [
  ["Abbott Bioline HBsAg Casette WB", "Bioline HbsAg Casette WB"],
  ["M53 - Diluent 20 L(1 Tank)", "CBC M53-Diluent 20 L (1Tank)440"],
  ["M53- Lyse LH(5x2 Bottle)", "CBC M53-Lyse LH (5*2Bottle)"],
  ["M53- Lyse LEO (I)(1 Lite/Bottle)", "CBC M53-Lyse LEO(I)(1Lite/BOX"],
  ["M53- Lyse LEO (II)(1 Lite/Bottle)", "CBC M53-Lyse LEO(II)(1Lite/Bottle"],
  ["M53 -Cleanser (50 ml./Bottle)", "CBC M53-Cleanser(50ml./Bottle)"],
  ["M53-Probe Cleanser(50 ml./Bottle)", "CBC M53-Probe Cleanser(50ml./Bottle)"],
  ["5MDR Low+Normal+High(3x3 ml.)", "CBC 5MDR Low+Normal+High(3*3 ml.)"],
  ["Determine HIV Early Detected", "Determine HIV Early Detect"],
  ["All Test HBsAg/HCV Combo Rapid Test Cassette", "All Test HBsAg/HCV Combo Rapid Test Cassette(25 Test/pack)"],
  ["Dengue NS1(25Test/box)", "Abbott Dengue NS1(25Test/box)", "Abbott Dengue NS1"],
  ["All Test HBsAg Rapid Test Cassette(40 Test/Box)", "All Test HBsAg Rapid Test Cassette"],
  ["All Test HCV Rapid Test Cassette( 40 Test/Box)", "All Test HCV Rapid Test Cassette"],
  ["Influenza A+B Rapid Test , Cessette", "Influenza A+B rapid test"],
  ["หลอดเป่าแอลกอฮอล์ รุ่น AT8070", "หลอดเครื่องเป่าแอลกอฮอล์ รุ่น AT8070"],
  ["เครื่องเป่าแอลกอฮอล์ รุ่น AT8070", "เครื่องเป่าแอลกอฮอล์"],
  ["เฝือกดามคอเด็ก ปรับ 12 ระดับ(Sam-Splint USA)", "เฝือกดามคอเด็ก ปรับ 12 ระดับ"],
  ["Abbott HAV IGG/IGM(D)", "HAV"],
]

PRIORITY = ["admin","service","device","consum","hema","rapid","chem"]


def cat(name):
    n = name.lower()
    if n.startswith("หลอด"):
        return "consum"
    for key in PRIORITY:
        for k, l, kws in CATS:
            if k != key:
                continue
            for kw in kws:
                if kw.lower() in n:
                    return k
    return "other"


# ---------------------------------------------------------------- ดึง / อ่าน CSV
def fetch_csv():
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "alphamdx-stock-sync/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def parse_qty(v):
    """ช่องคงเหลือ: ว่าง/ไม่ใช่เลข -> None ; gviz อาจส่งมาเป็น 50.0 หรือ 1,000"""
    s = (v or "").strip().replace(",", "")
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f == int(f) else None


def read_rows(text):
    """แถวแรกของ gviz เป็น header ที่รวมข้อความไว้ผิดรูป -> ตัดทิ้ง"""
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    out = []
    for r in rows[1:]:
        name = (r[0] if len(r) > 0 else "").strip()
        if not name:
            continue
        out.append({
            "n": name,
            "q": parse_qty(r[1] if len(r) > 1 else ""),
            "note": (r[2] if len(r) > 2 else "").strip(),
        })
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="อ่านจากไฟล์ CSV แทนการดึงจากชีต")
    ap.add_argument("--force", action="store_true", help="ข้าม guard เรื่องข้อมูลหาย")
    args = ap.parse_args()

    if args.csv:
        text = open(args.csv, encoding="utf-8").read()
        src = args.csv
    else:
        text = fetch_csv()
        src = SHEET_URL

    raw = read_rows(text)

    # ---- guard 1: จำนวนแถวขั้นต่ำ
    if len(raw) < MIN_ROWS:
        sys.exit("ล้มเหลว: ได้ {} แถวจาก {} (ต้องได้อย่างน้อย {}) — ไม่เขียน {}"
                 .format(len(raw), src, MIN_ROWS, OUT))

    # ---- ยอดรอบก่อน (สำหรับลูกศร ▼▲) + guard 2
    prev, prev_n = {}, None
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            prev = {i["n"]: i["q"] for i in old.get("items", [])}
            prev_n = len(old.get("items", []))
        except Exception as e:
            print("อ่าน {} รอบก่อนไม่ได้ ({}) — ไม่แสดงลูกศรรอบนี้".format(OUT, e))

    # ---- รวมแถวชื่อซ้ำที่จำนวนตรงกัน
    by_name = OrderedDict()
    for it in raw:
        by_name.setdefault(it["n"], []).append(it)

    items, merged = [], []
    for name, group in by_name.items():
        qs = {g["q"] for g in group}
        if len(group) > 1 and len(qs) == 1:
            note = next((g["note"] for g in group if g["note"]), "")
            items.append({"n": name, "q": group[0]["q"], "c": cat(name), "note": note, "dup": len(group)})
            merged.append((name, len(group)))
        else:
            for g in group:
                items.append({"n": name, "q": g["q"], "c": cat(name), "note": g["note"], "dup": 0})

    if prev_n and len(items) < prev_n * (1 - MAX_DROP) and not args.force:
        sys.exit("ล้มเหลว: รายการลดจาก {} เหลือ {} (เกิน {:.0%}) — ไม่เขียน {} "
                 "ถ้าชีตถูกลบจริงให้รันซ้ำด้วย --force"
                 .format(prev_n, len(items), MAX_DROP, OUT))

    present = {i["n"] for i in items}
    qmap = {i["n"]: i["q"] for i in items}
    dup_groups = []
    for g in DUP_GROUPS:
        g2 = [n for n in g if n in present]
        if len(g2) > 1:
            dup_groups.append([{"n": n, "q": qmap[n]} for n in g2])

    data = {
        "labels": LABELS,
        "order": ORDER,
        "nonstock": NONSTOCK,
        "items": items,
        "dupGroups": dup_groups,
        "prev": prev,
        "syncedAt": datetime.datetime.now(datetime.timezone.utc)
                    .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # ---- สรุปผล
    stock = [i for i in items if i["c"] not in NONSTOCK]
    need = [i for i in stock if i["q"] is not None and i["q"] <= 2]
    changed = [(i["n"], prev[i["n"]], i["q"]) for i in items
               if i["n"] in prev and prev[i["n"]] is not None
               and i["q"] is not None and i["q"] != prev[i["n"]]]

    print("แหล่งข้อมูล:", src)
    print("แถวในชีต:", len(raw), "| หลังรวมชื่อซ้ำ:", len(items), "| merged:", len(merged))
    print("สินค้าในคลัง:", len(stock), "| ไม่ใช่ของในคลัง:", len(items) - len(stock))
    print("  ต้องสั่งซื้อ:", len(need),
          "( หมด", sum(1 for i in stock if i["q"] == 0),
          "/ เหลือน้อย", sum(1 for i in stock if i["q"] is not None and 1 <= i["q"] <= 2), ")")
    print("  มีของพอ:", sum(1 for i in stock if i["q"] is not None and i["q"] > 2))
    print("  ยังไม่ระบุ:", sum(1 for i in stock if i["q"] is None))
    print("  หมวด:", dict(Counter(i["c"] for i in items)))
    print("  กลุ่มชื่อซ้ำที่ต้องรวมในชีต:", len(dup_groups))
    if changed:
        print("จำนวนเปลี่ยนจากรอบก่อน", len(changed), "รายการ:")
        for n, a, b in changed[:30]:
            print("   {} : {} -> {}".format(n, a, b))
    else:
        print("จำนวนไม่เปลี่ยนจากรอบก่อน")
    print("เขียน", OUT, "เรียบร้อย · syncedAt =", data["syncedAt"])


if __name__ == "__main__":
    main()
