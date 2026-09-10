# สต็อก Alpha MDX — เว็บไซต์

หน้าเว็บสต็อกอุปกรณ์และน้ำยาตรวจ ซิงค์อัตโนมัติจาก Google Sheet ทุกชั่วโมงด้วย GitHub Actions
แล้วเผยแพร่ผ่าน GitHub Pages ไม่ต้องมีเซิร์ฟเวอร์ ไม่ต้องพึ่ง Claude

## ไฟล์ในโปรเจกต์

| ไฟล์ | หน้าที่ |
|---|---|
| `index.html` | ตัวหน้าเว็บ (static ไฟล์เดียว) โหลด `data.json` ตอนเปิดหน้า |
| `data.json` | ข้อมูลสต็อกที่ซิงค์มาแล้ว — **สร้างอัตโนมัติ ไม่ต้องแก้มือ** |
| `build.py` | ดึง CSV จากชีต → จัดหมวดหมู่ → เขียน `data.json` |
| `.github/workflows/sync.yml` | ตั้งเวลาให้ `build.py` รันทุกชั่วโมงและ commit ผลลัพธ์ |

## ตั้งค่าครั้งแรก (ประมาณ 5 นาที)

1. **สร้าง repo** ใหม่บน GitHub ตั้งเป็น Public (Pages แบบฟรีต้องเป็น public)
   แล้วอัปโหลดไฟล์ทั้งหมดนี้ไว้ที่ราก repo — ผ่านหน้าเว็บ GitHub ก็ได้
   (Add file → Upload files ลากทั้งโฟลเดอร์ลงไป) หรือผ่าน git:
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main
   ```

2. **เปิดสิทธิ์ให้ Actions เขียน repo ได้**
   Settings → Actions → General → Workflow permissions →
   เลือก **Read and write permissions** → Save

3. **เปิด GitHub Pages**
   Settings → Pages → Source: **Deploy from a branch** →
   Branch: `main`, Folder: `/ (root)` → Save
   URL จะเป็น `https://<user>.github.io/<repo>/`

4. **สั่งซิงค์รอบแรกเอง**
   Actions → `sync-stock` → **Run workflow**
   รอ ~1 นาที จะเห็น commit `sync: …` และมีไฟล์ `data.json` โผล่ขึ้นมา
   จากนั้นเปิด URL ของ Pages ได้เลย

5. **(ถ้าต้องการ) ใช้โดเมนตัวเอง**
   Settings → Pages → Custom domain → ใส่โดเมน เช่น `stock.alphamdx.com`
   แล้วไปตั้ง DNS ที่ผู้ให้บริการโดเมน: `CNAME  stock  <user>.github.io`

## ชีตต้นทาง

`build.py` อ่านจาก endpoint นี้ (ไม่ต้องใช้ API key แต่ชีตต้องเปิดให้ "ผู้ที่มีลิงก์" ดูได้):

```
https://docs.google.com/spreadsheets/d/<SHEET_ID>/gviz/tq?tqx=out:csv&gid=0
```

ค่าเริ่มต้นฝังไว้ในหัวไฟล์ `build.py` เปลี่ยนได้ที่ตัวแปร `SHEET_ID` / `GID`
หรือส่งเป็น environment variable ก็ได้ (`SHEET_ID=... python3 build.py`)

โครงคอลัมน์ที่ต้องมี: **A = ชื่อสินค้า, B = คงเหลือ, C = หมายเหตุ** แถวแรกเป็นหัวตาราง

## กันข้อมูลพัง

`build.py` จะ **ไม่เขียน** `data.json` ถ้า:

- ได้แถวน้อยกว่า `MIN_ROWS` (ค่าเริ่มต้น 100) — กันกรณีชีตโหลดไม่ครบ
- จำนวนรายการลดจากรอบก่อนเกิน 20% — กันกรณีชีตถูกลบ/แชร์ปิด

เมื่อ guard ทำงาน workflow จะขึ้นสีแดงและ `data.json` เดิมยังอยู่ครบ
หน้าเว็บจึงยังแสดงข้อมูลรอบก่อนต่อไปได้ปกติ
ถ้าชีตลดลงจริงและต้องการให้เขียนทับ ให้รัน `python3 build.py --force` แล้ว commit เอง

## แก้/เพิ่มหมวดหมู่

คำค้นของแต่ละหมวดอยู่ในตัวแปร `CATS` ในไฟล์ `build.py`
ชื่อสินค้าจะถูกจับหมวดตามลำดับใน `PRIORITY` (แถวไหนไม่ตรงคำค้นไหนเลย → หมวด `other`)
กลุ่มชื่อที่รู้ว่าซ้ำกันแต่สะกดต่างกันอยู่ใน `DUP_GROUPS` แสดงเป็นพาเนลท้ายหน้าเว็บ

## ทดสอบในเครื่อง

```bash
python3 build.py                    # ดึงชีตจริง
python3 build.py --csv sample.csv   # ใช้ CSV ตัวอย่าง ไม่ต้องต่อเน็ต
python3 -m http.server 8000         # เปิด http://localhost:8000
```

> หมายเหตุ: cron ของ GitHub Actions อาจคลาดเวลาไปหลายนาทีในช่วงที่คนใช้เยอะ
> และจะถูกปิดอัตโนมัติถ้า repo ไม่มีความเคลื่อนไหว 60 วัน — แต่ workflow นี้ commit เองทุกชั่วโมง
> จึงถือว่ามีความเคลื่อนไหวอยู่เสมอ
